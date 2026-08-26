"""Deterministic import engine.

One media item = one unit of work: ``process_media_item`` syncs its TMDB
metadata then applies its tracking records. This module holds the pure-ish
helpers for that flow: grouping, per-item upserts (signal-free), mirror
deletion and the canonical status reconciliation.
"""

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .cache import cache as tracking_cache
from .choices import DataImportMode, MediaType, TvShowStatus, WatchEntryMediaType
from .import_records import (
    RATINGS_COLLECTION,
    WATCH_HISTORY_COLLECTION,
    WATCHLIST_COLLECTION,
    ParsedImport,
    RatingRecord,
    StatusRecord,
    WatchEntryRecord,
)
from .models import Rating, UserMediaStatus, WatchEntry
from .status_sync import refresh_show_status

_STATUS_FIELD_BY_STATE: dict[str, str] = {
    TvShowStatus.WATCHED: 'completed_at',
    TvShowStatus.DROPPED: 'dropped_at',
    TvShowStatus.PLAN_TO_WATCH: 'plan_to_watch_at',
}


def group_by_item(parsed: ParsedImport) -> list[dict]:
    """Group parsed records per media item, TV shows first, movies second.

    Returns JSON-safe payloads ready to be dispatched as task arguments:
    ``{'media_type': ..., 'tmdb_id': ..., 'records': [dict, ...]}``.
    """
    groups: dict[tuple[str, int], list[dict]] = {}
    order: list[tuple[str, int]] = []

    def push(media_type: str, tmdb_id: int, record: dict | None = None):
        key = (media_type, tmdb_id)
        if key not in groups:
            groups[key] = []
            order.append(key)
        if record is not None:
            groups[key].append(record)

    for record in parsed.sorted_records():
        if isinstance(record, WatchEntryRecord):
            parent = MediaType.TV if record.media_type == WatchEntryMediaType.EPISODE else MediaType.MOVIE
            push(parent, record.tmdb_id, _watch_entry_payload(record))
        elif isinstance(record, StatusRecord):
            push(record.media_type, record.tmdb_id, _status_payload_dict(record))
        else:
            push(record.media_type, record.tmdb_id, _rating_payload(record))

    for media_type, tmdb_ids in parsed.prefetch_only_ids.items():
        for tmdb_id in sorted(tmdb_ids):
            push(media_type, tmdb_id)

    return [
        {'media_type': media_type, 'tmdb_id': tmdb_id, 'records': groups[(media_type, tmdb_id)]}
        for media_type, tmdb_id in order
    ]


def _watch_entry_payload(record: WatchEntryRecord) -> dict:
    return {
        'kind': 'watch_entry',
        'media_type': record.media_type,
        'season_number': record.season_number,
        'episode_number': record.episode_number,
        'watched_at': record.watched_at.isoformat() if record.watched_at else None,
    }


def _status_payload_dict(record: StatusRecord) -> dict:
    return {
        'kind': 'status',
        'status': record.status,
        'status_at': record.status_at.isoformat() if record.status_at else None,
        'progress': record.progress,
    }


def _rating_payload(record: RatingRecord) -> dict:
    return {'kind': 'rating', 'score': record.score}


def _parse_dt(value):
    from django.utils.dateparse import parse_datetime

    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        return None
    from django.utils import timezone as tz

    return tz.make_aware(parsed) if tz.is_naive(parsed) else parsed


def _watch_entry_record(payload: dict, tmdb_id: int) -> WatchEntryRecord:
    return WatchEntryRecord(
        media_type=payload['media_type'],
        tmdb_id=tmdb_id,
        watched_at=_parse_dt(payload.get('watched_at')),
        season_number=payload.get('season_number'),
        episode_number=payload.get('episode_number'),
    )


def _status_record(payload: dict, media_type: str, tmdb_id: int) -> StatusRecord:
    return StatusRecord(
        media_type=media_type,
        tmdb_id=tmdb_id,
        status=payload['status'],
        status_at=_parse_dt(payload.get('status_at')),
        progress=payload.get('progress'),
    )


def _rating_record(media_type: str, tmdb_id: int, payload: dict) -> RatingRecord:
    return RatingRecord(media_type=media_type, tmdb_id=tmdb_id, score=payload['score'])


def apply_item_records(user, media_type: str, tmdb_id: int, payloads: list[dict], import_mode: str) -> int:
    """Upsert every tracking record of one media item without firing signals."""
    watch_entries = []
    statuses = []
    ratings = []
    for payload in payloads:
        kind = payload.get('kind')
        if kind == 'watch_entry':
            watch_entries.append(_watch_entry_record(payload, tmdb_id))
        elif kind == 'status':
            statuses.append(_status_record(payload, media_type, tmdb_id))
        elif kind == 'rating':
            ratings.append(_rating_record(media_type, tmdb_id, payload))

    applied = 0
    applied += _upsert_watch_entry(user, media_type, tmdb_id, watch_entries, import_mode)
    applied += _upsert_status(user, media_type, tmdb_id, statuses, import_mode)
    applied += _upsert_rating(user, media_type, tmdb_id, ratings, import_mode)
    return applied


def _upsert_watch_entry(user, media_type: str, tmdb_id: int, records: list[WatchEntryRecord], import_mode: str) -> int:
    """Upsert every watch entry of one item. Duplicate (season, episode) keys
    fold to their latest watched_at; existing rows follow import_mode."""
    if not records:
        return 0

    def event_ts(record: WatchEntryRecord) -> float:
        return record.watched_at.timestamp() if record.watched_at else float('-inf')

    folded: dict[tuple[int | None, int | None], WatchEntryRecord] = {}
    for record in records:
        key = (record.season_number, record.episode_number)
        current = folded.get(key)
        if current is None or event_ts(record) > event_ts(current):
            folded[key] = record

    entry_watch_type = (
        WatchEntryMediaType.EPISODE if media_type == MediaType.TV else WatchEntryMediaType.MOVIE
    )

    condition = Q()
    for season_number, episode_number in folded:
        condition |= Q(season_number=season_number, episode_number=episode_number)
    existing_map = {
        (entry.season_number, entry.episode_number): entry
        for entry in WatchEntry.objects.filter(
            user=user, media_type=entry_watch_type, tmdb_id=tmdb_id,
        ).filter(condition).iterator()
    }

    to_create = []
    to_update = []
    for (season_number, episode_number), record in folded.items():
        existing = existing_map.get((season_number, episode_number))
        if existing is None:
            to_create.append(
                WatchEntry(
                    user=user,
                    media_type=entry_watch_type,
                    tmdb_id=tmdb_id,
                    season_number=season_number,
                    episode_number=episode_number,
                    watched_at=record.watched_at,
                )
            )
            continue
        if import_mode == DataImportMode.NEW_ITEMS:
            continue
        new_watched_at = record.watched_at
        if existing.watched_at and record.watched_at:
            new_watched_at = max(existing.watched_at, record.watched_at)
        elif existing.watched_at:
            new_watched_at = existing.watched_at
        if new_watched_at != existing.watched_at:
            existing.watched_at = new_watched_at
            to_update.append(existing)

    with transaction.atomic():
        if to_create:
            WatchEntry.objects.bulk_create(to_create, batch_size=500, ignore_conflicts=True)
        if to_update:
            WatchEntry.objects.bulk_update(to_update, ['watched_at'], batch_size=500)
    return len(to_create) + len(to_update)


def _upsert_status(user, media_type: str, tmdb_id: int, records: list[StatusRecord], import_mode: str) -> int:
    if not records:
        return 0

    # Sorted input means the newest explicit status arrives last and wins.
    record = records[-1]
    effective_at = record.status_at or timezone.now()
    payload: dict = {'status': record.status, 'status_changed_at': effective_at}
    marker_field = _STATUS_FIELD_BY_STATE.get(record.status)
    if marker_field:
        payload[marker_field] = effective_at
    if media_type == MediaType.TV:
        payload['last_watched_at'] = effective_at

    existing = UserMediaStatus.objects.filter(user=user, media_type=media_type, tmdb_id=tmdb_id).first()
    if existing is None:
        if media_type == MediaType.TV:
            payload.setdefault('started_at', effective_at)
            payload['watched_episodes'] = record.progress or 0
            payload['total_episodes'] = 0
            payload['progress_percent'] = 0
        UserMediaStatus.objects.bulk_create(
            [UserMediaStatus(user=user, media_type=media_type, tmdb_id=tmdb_id, **payload)],
            ignore_conflicts=True,
        )
        return 1

    if import_mode == DataImportMode.NEW_ITEMS:
        return 0

    update_fields = [field for field, value in payload.items() if getattr(existing, field) != value]
    if not update_fields:
        return 0
    for field, value in payload.items():
        setattr(existing, field, value)
    UserMediaStatus.objects.bulk_update([existing], sorted(update_fields))
    return 1


def _upsert_rating(user, media_type: str, tmdb_id: int, records: list[RatingRecord], import_mode: str) -> int:
    if not records:
        return 0

    record = records[-1]  # sorted order: last wins
    existing = Rating.objects.filter(user=user, media_type=media_type, tmdb_id=tmdb_id).first()
    if existing is None:
        Rating.objects.bulk_create(
            [Rating(user=user, media_type=media_type, tmdb_id=tmdb_id, score=record.score)],
            ignore_conflicts=True,
        )
        return 1
    if import_mode == DataImportMode.NEW_ITEMS:
        return 0
    if existing.score != record.score:
        existing.score = record.score
        Rating.objects.bulk_update([existing], ['score'])
        return 1
    return 0


def _winning_statuses(parsed: ParsedImport) -> dict[tuple[str, int], StatusRecord]:
    winners: dict[tuple[str, int], StatusRecord] = {}
    for record in parsed.sorted_records():
        if isinstance(record, StatusRecord):
            winners[(record.media_type, record.tmdb_id)] = record
    return winners


def _history_ids(user, watch_media_type: str, tmdb_ids: set[int]) -> set[int]:
    if not tmdb_ids:
        return set()
    return set(
        WatchEntry.objects.filter(user=user, media_type=watch_media_type, tmdb_id__in=tmdb_ids).values_list(
            'tmdb_id', flat=True
        )
    )


def _last_history_event(user, watch_media_type: str, tmdb_id: int):
    entry = (
        WatchEntry.objects.filter(user=user, media_type=watch_media_type, tmdb_id=tmdb_id)
        .order_by('-watched_at', '-created_at', '-id')
        .first()
    )
    if entry is None:
        return None
    return entry.watched_at or entry.created_at or timezone.now()


def _write_movie_watched(user, tmdb_id: int, event_at):
    UserMediaStatus.objects.update_or_create(
        user=user,
        media_type=MediaType.MOVIE,
        tmdb_id=tmdb_id,
        defaults={
            'status': TvShowStatus.WATCHED,
            'completed_at': event_at,
            'last_watched_at': event_at,
            'status_changed_at': event_at,
            'progress_percent': 100,
        },
    )


def reconcile_user_media_status(user, parsed: ParsedImport):
    """Impose the canonical post-import state.

    TV rules: watching/watched are always derived from materialized episode
    entries (refresh_show_status); only plan_to_watch and dropped survive as
    explicit imported statuses — dropped overlays the derived status while
    keeping its refreshed episode counts. Shows without history take their
    explicit status as-is. Movies with history become watched."""
    winners = _winning_statuses(parsed)
    movie_ids = {r.tmdb_id for r in parsed.watch_entries() if r.media_type == WatchEntryMediaType.MOVIE}
    movie_ids |= {tid for (media, tid) in winners if media == MediaType.MOVIE}
    tv_ids = {r.tmdb_id for r in parsed.watch_entries() if r.media_type == WatchEntryMediaType.EPISODE}
    tv_ids |= {tid for (media, tid) in winners if media == MediaType.TV}

    movie_history = _history_ids(user, WatchEntryMediaType.MOVIE, movie_ids)
    tv_history = _history_ids(user, WatchEntryMediaType.EPISODE, tv_ids)

    for tmdb_id in movie_history:
        _write_movie_watched(user, tmdb_id, _last_history_event(user, WatchEntryMediaType.MOVIE, tmdb_id))

    for tmdb_id in movie_ids - movie_history:
        winner = winners.get((MediaType.MOVIE, tmdb_id))
        if winner is not None:
            _apply_status_winner(user, winner)

    for tmdb_id in tv_history:
        refresh_show_status(user.id, tmdb_id)
        winner = winners.get((MediaType.TV, tmdb_id))
        if winner is not None and winner.status == TvShowStatus.DROPPED:
            # Explicit dropped wins over the derived status; episode counts
            # computed by the refresh stay intact.
            dropped_at = winner.status_at or timezone.now()
            UserMediaStatus.objects.update_or_create(
                user=user,
                media_type=MediaType.TV,
                tmdb_id=tmdb_id,
                defaults={
                    'status': TvShowStatus.DROPPED,
                    'dropped_at': dropped_at,
                    'status_changed_at': dropped_at,
                },
            )

    for tmdb_id in tv_ids - tv_history:
        winner = winners.get((MediaType.TV, tmdb_id))
        if winner is not None:
            _apply_status_winner(user, winner)

    # Bulk writes skip signals, so cached stats/progress must be dropped here.
    tracking_cache.invalidate_user_stats(user.id)
    for tmdb_id in sorted(tv_ids):
        tracking_cache.invalidate_show_progress(user.id, tmdb_id)


def _apply_status_winner(user, record: StatusRecord):
    """Single-row absolute write used only by reconciliation (items without
    watch history)."""
    effective_at = record.status_at or timezone.now()
    payload: dict = {'status': record.status, 'status_changed_at': effective_at}
    marker_field = _STATUS_FIELD_BY_STATE.get(record.status)
    if marker_field:
        payload[marker_field] = effective_at
    if record.media_type == MediaType.TV:
        payload['last_watched_at'] = effective_at

    existing = UserMediaStatus.objects.filter(user=user, media_type=record.media_type, tmdb_id=record.tmdb_id).first()
    if existing is None:
        if record.media_type == MediaType.TV:
            payload.setdefault('started_at', effective_at)
            payload['watched_episodes'] = record.progress or 0
            payload['total_episodes'] = 0
            payload['progress_percent'] = 0
        UserMediaStatus.objects.create(user=user, media_type=record.media_type, tmdb_id=record.tmdb_id, **payload)
        return

    changed = False
    for field, value in payload.items():
        if getattr(existing, field) != value:
            setattr(existing, field, value)
            changed = True
    if changed:
        existing.save(update_fields=list(payload.keys()))


def delete_missing_rows(user, parsed: ParsedImport):
    """Mirror mode: delete tracked rows absent from the imported set."""
    watch_keys = {record.mirror_key() for record in parsed.watch_entries()}
    plan_keys = {(r.media_type, r.tmdb_id) for r in parsed.statuses() if r.status == TvShowStatus.PLAN_TO_WATCH}
    rating_keys = {(r.media_type, r.tmdb_id) for r in parsed.ratings()}
    collections_present = parsed.collections_present

    if WATCH_HISTORY_COLLECTION in collections_present:
        stale_ids = [
            entry.id
            for entry in WatchEntry.objects.filter(user=user)
            if (entry.media_type, entry.tmdb_id, entry.season_number, entry.episode_number) not in watch_keys
        ]
        if stale_ids:
            WatchEntry.objects.filter(id__in=stale_ids).delete()

    if WATCHLIST_COLLECTION in collections_present:
        stale_ids = [
            item.id
            for item in UserMediaStatus.objects.for_user(user).planning()
            if (item.media_type, item.tmdb_id) not in plan_keys
        ]
        if stale_ids:
            UserMediaStatus.objects.filter(id__in=stale_ids).delete()

    if RATINGS_COLLECTION in collections_present:
        stale_ids = [
            rating.id
            for rating in Rating.objects.filter(user=user)
            if (rating.media_type, rating.tmdb_id) not in rating_keys
        ]
        if stale_ids:
            Rating.objects.filter(id__in=stale_ids).delete()


def build_final_report(job, parsed: ParsedImport, applied_count: int, metadata_state: dict | None = None) -> dict:
    state = metadata_state or {}
    report = dict(parsed.report)
    records_seen = report.get('records_seen', 0)
    records_imported = applied_count + report.get('metadata_only_shows', 0)
    report.update(
        {
            'records_imported': records_imported,
            'records_skipped': max(0, records_seen - records_imported),
            'metadata_hits': state.get('metadata_hits', 0),
            'metadata_fetches': state.get('metadata_fetches', 0),
            'metadata_errors': state.get('metadata_errors', 0),
            'total_items': job.total_items,
        }
    )
    return report

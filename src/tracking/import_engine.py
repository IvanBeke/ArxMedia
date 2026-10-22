"""Deterministic import engine.

One media item = one unit of work: ``process_media_item`` syncs its TMDB
catalog metadata and TVMaze TV enrichment, then applies its tracking records. This module holds the pure-ish
helpers for that flow: grouping, per-item upserts (signal-free), mirror
deletion and the canonical status reconciliation.
"""

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from .choices import DataImportMode, MediaType, TvShowStatus, WatchEntryMediaType
from .import_records import (
    LISTS_COLLECTION,
    RATINGS_COLLECTION,
    WATCH_HISTORY_COLLECTION,
    WATCHLIST_COLLECTION,
    ParsedImport,
    RatingRecord,
    StatusRecord,
    WatchEntryRecord,
)
from .models import CustomList, ListItem, Rating, UserMediaStatus, WatchEntry
from .signals import suppress_watch_entry_delete_signals
from .status_sync import refresh_movie_status, refresh_show_status

_STATUS_FIELD_BY_STATE: dict[str, str] = {
    TvShowStatus.WATCHED: 'completed_at',
    TvShowStatus.DROPPED: 'dropped_at',
    TvShowStatus.PLAN_TO_WATCH: 'plan_to_watch_at',
}


def _restore_list_item_timestamps(items, sources):
    """Restore imported timestamps after bulk_create bypasses auto_now_add."""
    dated_items = []
    for created, source in zip(items, sources, strict=False):
        if source.added_at:
            created.added_at = source.added_at
            dated_items.append(created)
    if dated_items:
        ListItem.objects.bulk_update(dated_items, ['added_at'])


def group_by_item(parsed: ParsedImport) -> list[dict]:
    """Group parsed records per media item, TV shows first, movies second.

    Returns JSON-safe payloads ready to be dispatched as task arguments:
    ``{'media_type': ..., 'tmdb_id': ..., 'records': [dict, ...]}``.
    """
    groups: dict[tuple[str, int], list[dict]] = {}
    order: list[tuple[str, int]] = []

    for record in parsed.sorted_records():
        _push_parsed_record(record, groups, order)

    _push_prefetch_only_ids(parsed, groups, order)

    return [
        {'media_type': media_type, 'tmdb_id': tmdb_id, 'records': groups[(media_type, tmdb_id)]}
        for media_type, tmdb_id in order
    ]


def _push_parsed_record(record, groups, order):
    if isinstance(record, WatchEntryRecord):
        parent = MediaType.TV if record.media_type == WatchEntryMediaType.EPISODE else MediaType.MOVIE
        _push_group(groups, order, parent, record.tmdb_id, _watch_entry_payload(record))
        return
    if isinstance(record, StatusRecord):
        _push_group(groups, order, record.media_type, record.tmdb_id, _status_payload_dict(record))
        return
    _push_group(groups, order, record.media_type, record.tmdb_id, _rating_payload(record))


def _push_prefetch_only_ids(parsed, groups, order):
    for media_type, tmdb_ids in parsed.prefetch_only_ids.items():
        for tmdb_id in sorted(tmdb_ids):
            _push_group(groups, order, media_type, tmdb_id)


def _push_group(groups, order, media_type, tmdb_id, record: dict | None = None):
    key = (media_type, tmdb_id)
    if key not in groups:
        groups[key] = []
        order.append(key)
    if record is not None:
        groups[key].append(record)


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
    return {
        'kind': 'rating',
        'score': record.score,
        'rated_at': record.rated_at.isoformat() if record.rated_at else None,
    }


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
    return RatingRecord(media_type=media_type, tmdb_id=tmdb_id, score=payload['score'], rated_at=_parse_dt(payload.get('rated_at')))


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

    folded = _fold_watch_entries(records)
    entry_watch_type = (
        WatchEntryMediaType.EPISODE if media_type == MediaType.TV else WatchEntryMediaType.MOVIE
    )
    existing_map = _existing_watch_entries(user, entry_watch_type, tmdb_id, folded)

    to_create = []
    to_update: list[WatchEntry] = []
    for (season_number, episode_number), record in folded.items():
        existing = existing_map.get((season_number, episode_number))
        if existing is None:
            to_create.append(_new_watch_entry(user, entry_watch_type, tmdb_id, season_number, episode_number, record))
        else:
            _stage_watch_entry_update(existing, record, import_mode, to_update)

    _persist_watch_entries(to_create, to_update)
    return len(to_create) + len(to_update)


def _watch_event_ts(record: WatchEntryRecord) -> float:
    return record.watched_at.timestamp() if record.watched_at else float('-inf')


def _fold_watch_entries(records):
    folded: dict[tuple[int | None, int | None], WatchEntryRecord] = {}
    for record in records:
        key = (record.season_number, record.episode_number)
        current = folded.get(key)
        if current is None or _watch_event_ts(record) > _watch_event_ts(current):
            folded[key] = record
    return folded


def _existing_watch_entries(user, entry_watch_type, tmdb_id, folded):
    condition = Q()
    for season_number, episode_number in folded:
        condition |= Q(season_number=season_number, episode_number=episode_number)
    return {
        (entry.season_number, entry.episode_number): entry
        for entry in WatchEntry.objects.filter(
            user=user, media_type=entry_watch_type, tmdb_id=tmdb_id,
        ).filter(condition).iterator()
    }


def _new_watch_entry(user, entry_watch_type, tmdb_id, season_number, episode_number, record):
    return WatchEntry(
        user=user,
        media_type=entry_watch_type,
        tmdb_id=tmdb_id,
        season_number=season_number,
        episode_number=episode_number,
        watched_at=record.watched_at,
    )


def _merged_watch_date(existing, record: WatchEntryRecord):
    if existing.watched_at and record.watched_at:
        return max(existing.watched_at, record.watched_at)
    return existing.watched_at or record.watched_at


def _stage_watch_entry_update(existing, record: WatchEntryRecord, import_mode: str, to_update):
    if import_mode == DataImportMode.NEW_ITEMS:
        return
    if (new_watched_at := _merged_watch_date(existing, record)) != existing.watched_at:
        existing.watched_at = new_watched_at
        to_update.append(existing)


def _persist_watch_entries(to_create, to_update):
    with transaction.atomic():
        if to_create:
            WatchEntry.objects.bulk_create(to_create, batch_size=500, ignore_conflicts=True)
        if to_update:
            WatchEntry.objects.bulk_update(to_update, ['watched_at'], batch_size=500)


def _status_write_payload(status, media_type, effective_at) -> dict:
    """Absolute payload for a UserMediaStatus write; TV derives the watch dates."""
    payload: dict = {'status': status, 'status_changed_at': effective_at}
    marker_field = _STATUS_FIELD_BY_STATE.get(status)
    if marker_field:
        payload[marker_field] = effective_at
    if media_type == MediaType.TV:
        # plan_to_watch means not started with nothing watched: no dates,
        # and any stale values on existing rows are cleared.
        if status == TvShowStatus.PLAN_TO_WATCH:
            payload['last_watched_at'] = None
            payload['started_at'] = None
        else:
            payload['last_watched_at'] = effective_at
    return payload


def _create_status_kwargs(payload, media_type, progress) -> dict:
    """Create-time fields for a fresh status row: TV bookkeeping defaults."""
    full = dict(payload)
    if media_type == MediaType.TV:
        full.setdefault('started_at', full['status_changed_at'])
        full['watched_episodes'] = progress
        full['total_episodes'] = 0
        full['progress_percent'] = 0
    return full


def _apply_status_update(existing, payload) -> bool:
    """Merge payload into an existing status row; True when fields changed."""
    update_fields = [field for field, value in payload.items() if getattr(existing, field) != value]
    if not update_fields:
        return False
    for field, value in payload.items():
        setattr(existing, field, value)
    return True


def _apply_status_row(user, media_type: str, tmdb_id: int, payload: dict, progress: int | None, import_mode: str) -> int:
    existing = UserMediaStatus.objects.filter(user=user, media_type=media_type, tmdb_id=tmdb_id).first()
    if existing is None:
        create_kwargs = _create_status_kwargs(payload, media_type, progress)
        UserMediaStatus.objects.bulk_create(
            [UserMediaStatus(user=user, media_type=media_type, tmdb_id=tmdb_id, **create_kwargs)],
            ignore_conflicts=True,
        )
        return 1
    if import_mode == DataImportMode.NEW_ITEMS:
        return 0
    if not _apply_status_update(existing, payload):
        return 0
    UserMediaStatus.objects.bulk_update([existing], sorted(payload))
    return 1


def _upsert_status(user, media_type: str, tmdb_id: int, records: list[StatusRecord], import_mode: str) -> int:
    if not records:
        return 0

    # Sorted input means the newest explicit status arrives last and wins.
    record = records[-1]
    effective_at = record.status_at or timezone.now()
    payload = _status_write_payload(record.status, media_type, effective_at)
    return _apply_status_row(user, media_type, tmdb_id, payload, record.progress or 0, import_mode)


def _upsert_rating(user, media_type: str, tmdb_id: int, records: list[RatingRecord], import_mode: str) -> int:
    if not records:
        return 0

    record = records[-1]  # sorted order: last wins
    existing = Rating.objects.filter(user=user, media_type=media_type, tmdb_id=tmdb_id).first()
    if existing is None:
        return _create_rating(user, media_type, tmdb_id, record)
    if import_mode == DataImportMode.NEW_ITEMS:
        return 0
    if not (changed_fields := _apply_rating_update(existing, record)):
        return 0
    Rating.objects.bulk_update([existing], sorted(changed_fields))
    return 1


def _create_rating(user, media_type: str, tmdb_id: int, record: RatingRecord) -> int:
    created = Rating.objects.create(user=user, media_type=media_type, tmdb_id=tmdb_id, score=record.score)
    if record.rated_at is not None:
        # auto_now/auto_now_add would stamp import time: restore the source rating date instead.
        Rating.objects.filter(pk=created.pk).update(created_at=record.rated_at, updated_at=record.rated_at)
    return 1


def _apply_rating_update(existing, record: RatingRecord) -> list[str]:
    """Set the imported score/date on an existing rating; return changed fields."""
    updates: dict = {}
    if existing.score != record.score:
        updates['score'] = record.score
    if record.rated_at is not None and existing.updated_at != record.rated_at:
        updates['updated_at'] = record.rated_at
    if not updates:
        return []
    for field, value in updates.items():
        setattr(existing, field, value)
    return list(updates)


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
        .order_by(F('watched_at').desc(nulls_last=True), '-created_at', '-id')
        .first()
    )
    return entry.watched_at if entry else None


def _write_movie_watched(user, tmdb_id: int, event_at):
    UserMediaStatus.objects.update_or_create(
        user=user,
        media_type=MediaType.MOVIE,
        tmdb_id=tmdb_id,
        defaults={
            'status': TvShowStatus.WATCHED,
            'completed_at': event_at,
            'last_watched_at': event_at,
            # An unknown watch date (None) still changed the status now.
            'status_changed_at': event_at or timezone.now(),
            'progress_percent': 100,
        },
    )


def _import_movie_and_tv_ids(parsed, winners):
    movie_ids = _watch_entry_ids(parsed, WatchEntryMediaType.MOVIE) | _winning_ids(winners, MediaType.MOVIE)
    tv_ids = _watch_entry_ids(parsed, WatchEntryMediaType.EPISODE) | _winning_ids(winners, MediaType.TV)
    return movie_ids, tv_ids


def _watch_entry_ids(parsed, watch_media_type):
    return {r.tmdb_id for r in parsed.watch_entries() if r.media_type == watch_media_type}


def _winning_ids(winners, media_type):
    return {tid for (media, tid) in winners if media == media_type}


def touched_status_keys(parsed: ParsedImport) -> set[tuple[str, int]]:
    """Every (media_type, tmdb_id) whose UserMediaStatus row the import may
    write: items with watch history (derived statuses) plus explicit winners."""
    winners = _winning_statuses(parsed)
    movie_ids, tv_ids = _import_movie_and_tv_ids(parsed, winners)
    return {(MediaType.MOVIE, tid) for tid in movie_ids} | {(MediaType.TV, tid) for tid in tv_ids}


def reconcile_user_media_status(
    user,
    parsed: ParsedImport,
    import_mode: str | None = None,
    preexisting_status_keys: set[tuple[str, int]] | None = None,
):
    """Impose the canonical post-import state.

    TV rules: watching/watched are always derived from materialized episode
    entries (refresh_show_status); only plan_to_watch and dropped survive as
    explicit imported statuses — dropped overlays the derived status while
    keeping its refreshed episode counts. Shows without history take their
    explicit status as-is. Movies with history become watched.

    In NEW_ITEMS mode explicit imported statuses never overwrite a row that
    predates the import (matching the _upsert_* guards); derived state (movie
    watched from materialized history, TV refresh) still applies since it
    follows entries that themselves respected the mode. ``preexisting_status_keys``
    snapshots rows present before the import ran, so rows the import itself
    just created are still finalized (e.g. the dropped overlay)."""
    new_only = import_mode == DataImportMode.NEW_ITEMS
    preexisting = None if preexisting_status_keys is None else set(preexisting_status_keys)
    winners = _winning_statuses(parsed)
    movie_ids, tv_ids = _import_movie_and_tv_ids(parsed, winners)

    movie_history = _history_ids(user, WatchEntryMediaType.MOVIE, movie_ids)
    _reconcile_movies(user, winners, movie_history, movie_ids - movie_history, new_only)

    tv_history = _history_ids(user, WatchEntryMediaType.EPISODE, tv_ids)
    _reconcile_tv(user, winners, tv_history, tv_ids - tv_history, new_only, preexisting)


def _reconcile_movies(user, winners, movie_history, no_history_ids, new_only):
    for tmdb_id in movie_history:
        _write_movie_watched(user, tmdb_id, _last_history_event(user, WatchEntryMediaType.MOVIE, tmdb_id))
    for tmdb_id in no_history_ids:
        _apply_status_winner_if_present(user, winners, MediaType.MOVIE, tmdb_id, new_only)


def _reconcile_tv(user, winners, tv_history, no_history_ids, new_only, preexisting):
    for tmdb_id in tv_history:
        refresh_show_status(user.id, tmdb_id)
        _apply_tv_dropped(user, tmdb_id, _tv_dropped_winner(winners.get((MediaType.TV, tmdb_id))), new_only, preexisting)
    for tmdb_id in no_history_ids:
        _apply_status_winner_if_present(user, winners, MediaType.TV, tmdb_id, new_only)


def _apply_status_winner_if_present(user, winners, media_type, tmdb_id, new_only):
    winner = winners.get((media_type, tmdb_id))
    if winner is not None:
        _apply_status_winner(user, winner, skip_existing=new_only)


def _tv_dropped_winner(winner):
    """Only the explicit dropped import status overlays the derived TV state."""
    if winner is not None and winner.status == TvShowStatus.DROPPED:
        return winner
    return None


def _apply_tv_dropped(user, tmdb_id, winner, new_only, preexisting):
    if winner is None:
        return
    if new_only and _has_preexisting_status(user, tmdb_id, preexisting):
        return
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


def _has_preexisting_status(user, tmdb_id, preexisting):
    if preexisting is not None:
        return (MediaType.TV, tmdb_id) in preexisting
    return UserMediaStatus.objects.for_user(user).for_media(MediaType.TV).filter(tmdb_id=tmdb_id).exists()


def _apply_status_winner(user, record: StatusRecord, skip_existing: bool = False):
    """Single-row absolute write used only by reconciliation (items without
    watch history)."""
    effective_at = record.status_at or timezone.now()
    payload = _status_write_payload(record.status, record.media_type, effective_at)
    existing = UserMediaStatus.objects.filter(user=user, media_type=record.media_type, tmdb_id=record.tmdb_id).first()
    if existing is None:
        create_kwargs = _create_status_kwargs(payload, record.media_type, record.progress or 0)
        UserMediaStatus.objects.create(user=user, media_type=record.media_type, tmdb_id=record.tmdb_id, **create_kwargs)
        return
    if skip_existing:
        return
    _save_status_changes(existing, payload)


def _save_status_changes(existing, payload):
    if _apply_status_update(existing, payload):
        existing.save(update_fields=list(payload.keys()))


def delete_missing_rows(user, parsed: ParsedImport):
    """Mirror mode: delete tracked rows absent from the imported set."""
    deleted = {
        WATCH_HISTORY_COLLECTION: 0,
        WATCHLIST_COLLECTION: 0,
        RATINGS_COLLECTION: 0,
    }
    collections_present = parsed.collections_present

    if WATCH_HISTORY_COLLECTION in collections_present:
        deleted[WATCH_HISTORY_COLLECTION] = _delete_stale_watch_entries(user, parsed)
    if WATCHLIST_COLLECTION in collections_present:
        deleted[WATCHLIST_COLLECTION] = _delete_stale_watchlist(user, parsed)
    if RATINGS_COLLECTION in collections_present:
        deleted[RATINGS_COLLECTION] = _delete_stale_ratings(user, parsed)
    if LISTS_COLLECTION in collections_present:
        deleted[LISTS_COLLECTION] = _delete_stale_lists(user, parsed)
    return deleted


def _delete_stale_watch_entries(user, parsed: ParsedImport) -> int:
    stale = _stale_watch_entries(user, _watch_mirror_keys(parsed))
    if not stale:
        return 0
    _delete_mirrored_watch_entries(stale)
    _refresh_deleted_watch_media(user, stale)
    return len(stale)


def _watch_mirror_keys(parsed: ParsedImport):
    return {record.mirror_key() for record in parsed.watch_entries()}


def _stale_watch_entries(user, watch_keys):
    return [
        entry
        for entry in WatchEntry.objects.filter(user=user)
        if (entry.media_type, entry.tmdb_id, entry.season_number, entry.episode_number) not in watch_keys
    ]


def _delete_mirrored_watch_entries(stale):
    # Skip the per-row post_delete handler; refresh each affected
    # title once instead.
    with suppress_watch_entry_delete_signals():
        WatchEntry.objects.filter(id__in=[entry.id for entry in stale]).delete()


def _refresh_deleted_watch_media(user, stale):
    affected_movies, affected_shows = _stale_media_ids(stale)
    for tmdb_id in affected_movies:
        refresh_movie_status(user.id, tmdb_id)
    for tmdb_id in affected_shows:
        refresh_show_status(user.id, tmdb_id)


def _stale_media_ids(stale):
    affected_movies = set()
    affected_shows = set()
    for entry in stale:
        if entry.media_type == WatchEntryMediaType.EPISODE:
            affected_shows.add(entry.tmdb_id)
        else:
            affected_movies.add(entry.tmdb_id)
    return affected_movies, affected_shows


def _delete_stale_watchlist(user, parsed: ParsedImport) -> int:
    plan_keys = _imported_watchlist_keys(parsed)
    stale_ids = [
        item.id
        for item in UserMediaStatus.objects.for_user(user).planning()
        if (item.media_type, item.tmdb_id) not in plan_keys
    ]
    if stale_ids:
        UserMediaStatus.objects.filter(id__in=stale_ids).delete()
    return len(stale_ids)


def _imported_watchlist_keys(parsed: ParsedImport):
    return {(r.media_type, r.tmdb_id) for r in parsed.statuses() if r.status == TvShowStatus.PLAN_TO_WATCH}


def _delete_stale_ratings(user, parsed: ParsedImport) -> int:
    rating_keys = {(r.media_type, r.tmdb_id) for r in parsed.ratings()}
    stale_ids = [
        rating.id
        for rating in Rating.objects.filter(user=user)
        if (rating.media_type, rating.tmdb_id) not in rating_keys
    ]
    if stale_ids:
        Rating.objects.filter(id__in=stale_ids).delete()
    return len(stale_ids)


def _delete_stale_lists(user, parsed: ParsedImport) -> int:
    imported_names = {record.name for record in parsed.lists}
    stale_lists = list(CustomList.objects.filter(user=user).exclude(name__in=imported_names))
    for custom_list in stale_lists:
        custom_list.delete()
    return len(stale_lists)


def _empty_list_counts() -> dict[str, int]:
    return {'lists_created': 0, 'lists_updated': 0, 'items_created': 0, 'items_updated': 0, 'items_deleted': 0}


def apply_imported_lists(user, parsed: ParsedImport, import_mode: str) -> dict[str, int]:
    """Restore owned lists and ordered items without creating collaborators."""
    applied = _empty_list_counts()
    for record in parsed.lists:
        _apply_list_record(user, record, import_mode, applied)
    return applied


def _apply_list_record(user, record, import_mode: str, applied):
    custom_list = _find_or_create_list(user, record, import_mode, applied)
    if import_mode == 'mirror_imported_set':
        deleted_items, _ = ListItem.objects.filter(custom_list=custom_list).delete()
        applied['items_deleted'] += deleted_items
    _sync_list_items(custom_list, record, import_mode, applied)


def _find_or_create_list(user, record, import_mode: str, applied):
    custom_list = _owned_list_by_name(user, record.name)
    if custom_list is None:
        return _create_list(user, record, applied)
    if import_mode != 'new_items':
        _update_list(custom_list, record, applied)
    return custom_list


def _create_list(user, record, applied):
    custom_list = CustomList.objects.create(
        user=user,
        name=record.name,
        description=record.description,
        privacy=record.privacy,
    )
    applied['lists_created'] += 1
    return custom_list


def _update_list(custom_list, record, applied):
    custom_list.description = record.description
    custom_list.privacy = record.privacy
    custom_list.save(update_fields=['description', 'privacy', 'updated_at'])
    applied['lists_updated'] += 1


def _owned_list_by_name(user, name):
    return next(
        (
            candidate
            for candidate in CustomList.objects.filter(user=user)
            if candidate.name.casefold() == name.casefold()
        ),
        None,
    )


def _sync_list_items(custom_list, record, import_mode: str, applied):
    existing_items = {
        (item.media_type, item.tmdb_id): item
        for item in ListItem.objects.filter(custom_list=custom_list)
    }
    to_create, create_sources, to_update = _plan_list_items(record, custom_list, existing_items, import_mode)
    if to_create:
        ListItem.objects.bulk_create(to_create)
        _restore_list_item_timestamps(to_create, create_sources)
        applied['items_created'] += len(to_create)
    if to_update:
        ListItem.objects.bulk_update(to_update, ['custom_order'])
        applied['items_updated'] += len(to_update)


def _plan_list_items(record, custom_list, existing_items, import_mode: str):
    to_create = []
    create_sources = []
    to_update: list[ListItem] = []
    for item in record.items:
        key = (item.media_type, item.tmdb_id)
        if key in existing_items:
            _stage_list_item_update(existing_items[key], item, import_mode, to_update)
            continue
        to_create.append(ListItem(
            custom_list=custom_list,
            media_type=item.media_type,
            tmdb_id=item.tmdb_id,
            added_at=item.added_at,
            custom_order=item.custom_order,
        ))
        create_sources.append(item)
    return to_create, create_sources, to_update


def _stage_list_item_update(existing_item, item, import_mode: str, to_update):
    if import_mode == 'update_existing' and existing_item.custom_order != item.custom_order:
        existing_item.custom_order = item.custom_order
        to_update.append(existing_item)


def _list_details(parsed: ParsedImport) -> list[dict]:
    """Per-list breakdown for the import report, with catalog titles when known."""
    from media.models import Movie, TVShow

    movie_ids = {item.tmdb_id for record in parsed.lists for item in record.items if item.media_type == MediaType.MOVIE}
    tv_ids = {item.tmdb_id for record in parsed.lists for item in record.items if item.media_type == MediaType.TV}
    movie_titles = dict(Movie.objects.filter(tmdb_id__in=movie_ids).values_list('tmdb_id', 'title')) if movie_ids else {}
    show_titles = dict(TVShow.objects.filter(tmdb_id__in=tv_ids).values_list('tmdb_id', 'name')) if tv_ids else {}
    details = []
    for record in parsed.lists:
        items = []
        for item in record.items:
            title = movie_titles.get(item.tmdb_id) if item.media_type == MediaType.MOVIE else show_titles.get(item.tmdb_id)
            items.append({'media_type': item.media_type, 'tmdb_id': item.tmdb_id, 'title': title})
        details.append({'name': record.name, 'privacy': record.privacy, 'items': items})
    return details


def build_final_report(job, parsed: ParsedImport, applied_count: int, metadata_state: dict | None = None, list_counts: dict | None = None) -> dict:
    state = metadata_state or {}
    report = dict(parsed.report)
    # Skipped = rows rejected at parse time; mode-skips/no-change land in
    # records_unchanged below. metadata_only_shows (Trakt watched-shows.json)
    # emit no tracking rows, so they must not inflate records_imported.
    records_imported = applied_count
    list_counts = list_counts or {
        'lists_created': 0,
        'lists_updated': 0,
        'items_created': 0,
        'items_updated': 0,
        'items_deleted': 0,
    }
    report.update(
        {
            'records_imported': records_imported,
            'records_skipped': max(0, parsed.invalid_count),
            'records_unchanged': max(0, len(parsed.records) - applied_count),
            'metadata_hits': state.get('metadata_hits', 0),
            'metadata_fetches': state.get('metadata_fetches', 0),
            'metadata_errors': state.get('metadata_errors', 0),
            'total_items': job.total_items,
            'lists_created': list_counts['lists_created'],
            'lists_updated': list_counts['lists_updated'],
            'list_items_created': list_counts['items_created'],
            'list_items_updated': list_counts['items_updated'],
            'list_items_deleted': list_counts['items_deleted'],
            'list_details': _list_details(parsed),
        }
    )
    return report

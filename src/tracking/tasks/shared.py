import csv
import io
import json
import logging
import re
import zipfile
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from django.utils import timezone
from media.models import Movie, Season, TVShow
from media.tmdb import tmdb

from ..choices import (
    DataImportMode,
    DataTransferFormat,
    DataTransferStatus,
    MediaType,
    TvShowStatus,
    WatchEntryMediaType,
    WatchEntryStatus,
)
from ..models import DataTransferJob, Rating, UserTvShowStatus, WatchEntry, Watchlist
from ..status_sync import refresh_show_and_season_statuses

logger = logging.getLogger(__name__)


YAMTRACK_IMPORT_SOURCE = 'yamtrack'
YAMTRACK_ALLOWED_MEDIA_TYPES = {'movie', 'tv', 'season', 'episode'}
YAMTRACK_ALLOWED_STATUSES = {'Completed', 'In progress', 'Planning', 'Paused', 'Dropped', ''}


def _safe_int(value):
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_watched_at(value: str | None):
    if not value:
        return None
    normalized = f'{value[:-1]}+00:00' if value.endswith('Z') else value
    try:
        dt = datetime.fromisoformat(normalized)
    except Exception:
        return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _parse_yamtrack_score(value) -> int | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        rounded = int(Decimal(raw).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError):
        return None
    if rounded <= 0:
        return None
    return min(rounded, 10)


def _parse_yamtrack_progress(value) -> int | None:
    parsed = _safe_int(value)
    if parsed is None or parsed < 0:
        return None
    return parsed


def _yamtrack_row_timestamp(row: dict, *fields: str):
    for field in fields:
        parsed = _parse_watched_at(row.get(field))
        if parsed:
            return parsed
    return None


def _yamtrack_watch_entry_status(value: str) -> str | None:
    mapping = {
        'Completed': WatchEntryStatus.WATCHED,
        'In progress': WatchEntryStatus.WATCHING,
        'Paused': WatchEntryStatus.WATCHING,
        'Dropped': WatchEntryStatus.DROPPED,
    }
    return mapping.get(value)


def _yamtrack_tv_status(value: str) -> str | None:
    mapping = {
        'Completed': TvShowStatus.WATCHED,
        'In progress': TvShowStatus.WATCHING,
        'Paused': TvShowStatus.WATCHING,
        'Planning': TvShowStatus.PLAN_TO_WATCH,
        'Dropped': TvShowStatus.DROPPED,
    }
    return mapping.get(value)


def _import_watch_entry_status_by_mode(
    user,
    media_type: str,
    tmdb_id: int,
    status_value: str,
    watched_at,
    import_mode: str,
    season_number: int | None = None,
    episode_number: int | None = None,
) -> bool:
    existing = WatchEntry.objects.filter(
        user=user,
        media_type=media_type,
        tmdb_id=tmdb_id,
        season_number=season_number,
        episode_number=episode_number,
    ).first()
    if existing and import_mode == DataImportMode.NEW_ITEMS:
        return False

    if not existing:
        WatchEntry.objects.create(
            user=user,
            media_type=media_type,
            tmdb_id=tmdb_id,
            season_number=season_number,
            episode_number=episode_number,
            status=status_value,
            watched_at=watched_at,
        )
        return True

    update_fields = []
    if existing.status != status_value:
        existing.status = status_value
        update_fields.append('status')

    if watched_at:
        if status_value == WatchEntryStatus.WATCHED and existing.watched_at:
            next_watched_at = max(existing.watched_at, watched_at)
        else:
            next_watched_at = watched_at
        if next_watched_at != existing.watched_at:
            existing.watched_at = next_watched_at
            update_fields.append('watched_at')

    if not update_fields:
        return False

    existing.save(update_fields=update_fields)
    return True


def _import_tv_status_by_mode(user, tmdb_id: int, status_value: str, status_at, progress: int | None, import_mode: str) -> bool:
    existing = UserTvShowStatus.objects.filter(user=user, tmdb_id=tmdb_id).first()
    if existing and import_mode == DataImportMode.NEW_ITEMS:
        return False

    payload: dict[str, Any] = {
        'status': status_value,
    }

    if status_value == TvShowStatus.WATCHED:
        payload['completed_at'] = status_at
    elif status_value == TvShowStatus.PLAN_TO_WATCH:
        payload['plan_to_watch_at'] = status_at
    elif status_value == TvShowStatus.DROPPED:
        payload['dropped_at'] = status_at

    if status_value in (TvShowStatus.WATCHING, TvShowStatus.WATCHED):
        payload['last_watched_at'] = status_at
        if existing is None:
            payload['started_at'] = status_at

    payload['status_changed_at'] = status_at
    if progress is not None:
        payload['watched_episodes'] = progress

    if existing is None:
        defaults = {
            'status': status_value,
            'watched_episodes': progress or 0,
            'total_episodes': 0,
            'progress_percent': 0,
            'started_at': status_at if status_value in (TvShowStatus.WATCHING, TvShowStatus.WATCHED) else None,
            'completed_at': status_at if status_value == TvShowStatus.WATCHED else None,
            'dropped_at': status_at if status_value == TvShowStatus.DROPPED else None,
            'plan_to_watch_at': status_at if status_value == TvShowStatus.PLAN_TO_WATCH else None,
            'last_watched_at': status_at if status_value in (TvShowStatus.WATCHING, TvShowStatus.WATCHED) else None,
            'status_changed_at': status_at,
        }
        UserTvShowStatus.objects.create(user=user, tmdb_id=tmdb_id, **defaults)
        return True

    changed = False
    for key, value in payload.items():
        if getattr(existing, key) != value:
            setattr(existing, key, value)
            changed = True
    if changed:
        existing.save(update_fields=list(payload.keys()))
    return changed


def _default_yamtrack_report() -> dict:
    return {
        'format': DataTransferFormat.CSV,
        'import_source': YAMTRACK_IMPORT_SOURCE,
        'records_seen': 0,
        'records_imported': 0,
        'records_skipped': 0,
        'metadata_hits': 0,
        'metadata_fetches': 0,
        'metadata_errors': 0,
        'skipped_non_tmdb': 0,
        'skipped_unsupported_media_type': 0,
        'skipped_invalid_status': 0,
        'skipped_missing_tmdb_id': 0,
        'summary': {
            'watch_history': 0,
            'watchlist': 0,
            'ratings': 0,
        },
        'total_items': 0,
    }


def _yamtrack_collection_from_row(media_type: str, status: str, score: int | None, end_at) -> set[str]:
    collections = set()
    if media_type == 'movie':
        if status in {'Completed', 'In progress', 'Paused', 'Dropped'}:
            collections.add('watch_history')
        if status == 'Planning':
            collections.add('watchlist')
    elif media_type == 'episode':
        if status in {'Completed', 'In progress', 'Paused', 'Dropped'} or not status and end_at:
            collections.add('watch_history')
    elif media_type == 'tv':
        if status == 'Planning':
            collections.add('watchlist')

    if media_type in {'movie', 'tv'} and score:
        collections.add('ratings')
    return collections


def _analyze_yamtrack_csv(content: bytes) -> dict:
    report = _default_yamtrack_report()
    reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig')))

    for row in reader:
        report['records_seen'] += 1
        source = (row.get('source') or '').strip().lower()
        media_type = (row.get('media_type') or '').strip().lower()
        status = (row.get('status') or '').strip()
        score = _parse_yamtrack_score(row.get('score'))
        end_at = _parse_watched_at(row.get('end_date'))

        if source != 'tmdb':
            report['records_skipped'] += 1
            report['skipped_non_tmdb'] += 1
            continue
        if media_type not in YAMTRACK_ALLOWED_MEDIA_TYPES:
            report['records_skipped'] += 1
            report['skipped_unsupported_media_type'] += 1
            continue
        if status not in YAMTRACK_ALLOWED_STATUSES:
            report['records_skipped'] += 1
            report['skipped_invalid_status'] += 1
            continue
        if _safe_int(row.get('media_id')) is None:
            report['records_skipped'] += 1
            report['skipped_missing_tmdb_id'] += 1
            continue

        categories = _yamtrack_collection_from_row(media_type, status, score, end_at)
        if categories:
            report['records_imported'] += 1
            for category in categories:
                report['summary'][category] += 1
        else:
            report['records_skipped'] += 1

    report['total_items'] = report['records_seen']
    return report


def _apply_yamtrack_csv(job: DataTransferJob, content: bytes, import_mode: str):
    report = _default_yamtrack_report()
    state = {
        'metadata_checked': set(),
        'season_checked': set(),
        'metadata_hits': 0,
        'metadata_fetches': 0,
        'metadata_errors': 0,
    }
    imported_keys: dict[str, set[tuple[object, ...]]] = {
        'watch_entries': set(),
        'watchlist': set(),
        'ratings': set(),
    }
    collections_present = set()
    explicit_show_status_ids = set()
    season_numbers_by_show: dict[int, set[int]] = {}

    reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig')))
    for row in reader:
        report['records_seen'] += 1
        source = (row.get('source') or '').strip().lower()
        media_type = (row.get('media_type') or '').strip().lower()
        status = (row.get('status') or '').strip()
        tmdb_id = _safe_int(row.get('media_id'))
        season_number = _safe_int(row.get('season_number'))
        episode_number = _safe_int(row.get('episode_number'))
        score = _parse_yamtrack_score(row.get('score'))
        notes = row.get('notes') or ''
        progress = _parse_yamtrack_progress(row.get('progress'))
        event_at = _yamtrack_row_timestamp(row, 'end_date', 'progressed_at', 'start_date', 'created_at')
        end_at = _parse_watched_at(row.get('end_date'))

        row_categories = _yamtrack_collection_from_row(media_type, status, score, end_at)
        for category in row_categories:
            collections_present.add(category)

        if source != 'tmdb':
            report['records_skipped'] += 1
            report['skipped_non_tmdb'] += 1
            job.processed_items += 1
            _update_job_progress(job)
            continue
        if media_type not in YAMTRACK_ALLOWED_MEDIA_TYPES:
            report['records_skipped'] += 1
            report['skipped_unsupported_media_type'] += 1
            job.processed_items += 1
            _update_job_progress(job)
            continue
        if status not in YAMTRACK_ALLOWED_STATUSES:
            report['records_skipped'] += 1
            report['skipped_invalid_status'] += 1
            job.processed_items += 1
            _update_job_progress(job)
            continue
        if not tmdb_id:
            report['records_skipped'] += 1
            report['skipped_missing_tmdb_id'] += 1
            job.processed_items += 1
            _update_job_progress(job)
            continue

        row_imported = False

        if media_type == 'movie':
            _ensure_tmdb_metadata_for_import_item(MediaType.MOVIE, tmdb_id, state)
            if status in {'Completed', 'In progress', 'Paused', 'Dropped'}:
                imported_keys['watch_entries'].add(_watch_entry_key(WatchEntryMediaType.MOVIE, tmdb_id))
                entry_status = _yamtrack_watch_entry_status(status)
                if entry_status and _import_watch_entry_status_by_mode(
                    job.user,
                    WatchEntryMediaType.MOVIE,
                    tmdb_id,
                    entry_status,
                    event_at,
                    import_mode,
                ):
                    row_imported = True
            if status == 'Planning':
                imported_keys['watchlist'].add(_watchlist_key(MediaType.MOVIE, tmdb_id))
                if _import_watchlist_by_mode(job.user, MediaType.MOVIE, tmdb_id, notes, import_mode):
                    row_imported = True
            if score:
                imported_keys['ratings'].add(_rating_key(MediaType.MOVIE, tmdb_id))
                if _import_rating_by_mode(job.user, MediaType.MOVIE, tmdb_id, score, import_mode):
                    row_imported = True

        elif media_type == 'tv':
            _ensure_tmdb_metadata_for_import_item(MediaType.TV, tmdb_id, state)
            tv_status = _yamtrack_tv_status(status)
            if tv_status:
                explicit_show_status_ids.add(tmdb_id)
                if _import_tv_status_by_mode(job.user, tmdb_id, tv_status, event_at, progress, import_mode):
                    row_imported = True
            if status == 'Planning':
                imported_keys['watchlist'].add(_watchlist_key(MediaType.TV, tmdb_id))
                if _import_watchlist_by_mode(job.user, MediaType.TV, tmdb_id, notes, import_mode):
                    row_imported = True
            if score:
                imported_keys['ratings'].add(_rating_key(MediaType.TV, tmdb_id))
                if _import_rating_by_mode(job.user, MediaType.TV, tmdb_id, score, import_mode):
                    row_imported = True

        elif media_type == 'season':
            _ensure_tmdb_metadata_for_import_item(WatchEntryMediaType.EPISODE, tmdb_id, state, season_number=season_number)
            tv_status = _yamtrack_tv_status(status)
            if tv_status:
                explicit_show_status_ids.add(tmdb_id)
                if _import_tv_status_by_mode(job.user, tmdb_id, tv_status, event_at, progress, import_mode):
                    row_imported = True

        elif media_type == 'episode':
            _ensure_tmdb_metadata_for_import_item(WatchEntryMediaType.EPISODE, tmdb_id, state, season_number=season_number)
            if season_number is not None:
                season_numbers_by_show.setdefault(tmdb_id, set()).add(season_number)

            entry_status = _yamtrack_watch_entry_status(status)
            if not entry_status and end_at:
                entry_status = WatchEntryStatus.WATCHED

            if entry_status and season_number is not None and episode_number is not None:
                imported_keys['watch_entries'].add(_watch_entry_key(WatchEntryMediaType.EPISODE, tmdb_id, season_number, episode_number))
                if _import_watch_entry_status_by_mode(
                    job.user,
                    WatchEntryMediaType.EPISODE,
                    tmdb_id,
                    entry_status,
                    event_at,
                    import_mode,
                    season_number=season_number,
                    episode_number=episode_number,
                ):
                    row_imported = True

        if row_imported:
            report['records_imported'] += 1
        else:
            report['records_skipped'] += 1

        job.processed_items += 1
        _update_job_progress(job)

    if import_mode == DataImportMode.MIRROR_IMPORTED_SET:
        _apply_mirror_deletions(job, imported_keys, collections_present)

    refresh_ids = set(season_numbers_by_show.keys()) - explicit_show_status_ids
    for tmdb_id in refresh_ids:
        refresh_show_and_season_statuses(job.user.id, tmdb_id, season_numbers_by_show.get(tmdb_id, set()))

    report['metadata_hits'] = state['metadata_hits']
    report['metadata_fetches'] = state['metadata_fetches']
    report['metadata_errors'] = state['metadata_errors']
    report['summary'] = {
        'watch_history': len(imported_keys['watch_entries']),
        'watchlist': len(imported_keys['watchlist']),
        'ratings': len(imported_keys['ratings']),
    }
    report['total_items'] = job.total_items
    job.metadata = report
    job.save(update_fields=['total_items', 'processed_items', 'metadata', 'updated_at'])


def _zip_json_sort_key(name: str):
    file_name = name.rsplit('/', 1)[-1].lower()
    match = re.match(r'^(.*?)-(\d+)\.json$', file_name)
    if match:
        return match.group(1), int(match.group(2)), file_name
    return file_name, 0, file_name


def _default_import_report() -> dict:
    return {
        'format': DataTransferFormat.ZIP,
        'files_processed': 0,
        'files_failed': 0,
        'records_seen': 0,
        'records_imported': 0,
        'records_skipped': 0,
        'metadata_hits': 0,
        'metadata_fetches': 0,
        'metadata_errors': 0,
        'unsupported_files': 0,
        'unsupported_records': 0,
        'files': [],
    }


def _update_job_progress(job: DataTransferJob, save_every: int = 25):
    if job.processed_items % save_every == 0:
        job.save(update_fields=['total_items', 'processed_items', 'metadata', 'updated_at'])


def _upsert_watch_entry(
    user,
    media_type: str,
    tmdb_id: int,
    watched_at,
    season_number: int | None = None,
    episode_number: int | None = None,
):
    entry, created = WatchEntry.objects.get_or_create(
        user=user,
        media_type=media_type,
        tmdb_id=tmdb_id,
        season_number=season_number,
        episode_number=episode_number,
        defaults={
            'status': WatchEntryStatus.WATCHED,
            'watched_at': watched_at,
        },
    )
    if created:
        return 'created'

    new_watched_at = watched_at if watched_at else entry.watched_at
    if entry.watched_at and watched_at:
        new_watched_at = max(entry.watched_at, watched_at)

    needs_update = entry.status != WatchEntryStatus.WATCHED or new_watched_at != entry.watched_at
    if needs_update:
        entry.status = WatchEntryStatus.WATCHED
        entry.watched_at = new_watched_at
        entry.save(update_fields=['status', 'watched_at'])
        return 'updated'
    return 'unchanged'


def _ensure_tv_season_metadata(tmdb_id: int, season_number: int | None, state: dict):
    if season_number is None:
        return

    season_key = (tmdb_id, season_number)
    if season_key in state['season_checked']:
        return

    show = TVShow.objects.filter(tmdb_id=tmdb_id).first()
    if not show:
        state['metadata_errors'] += 1
        state['season_checked'].add(season_key)
        return

    if Season.objects.filter(show=show, season_number=season_number).exists():
        state['metadata_hits'] += 1
        state['season_checked'].add(season_key)
        return

    try:
        tmdb.sync_season(show, season_number)
        state['metadata_fetches'] += 1
    except Exception as exc:
        state['metadata_errors'] += 1
        logger.warning('Failed season metadata sync for tv %s season %s: %s', tmdb_id, season_number, exc)
    state['season_checked'].add(season_key)


def _ensure_tmdb_metadata_for_import_item(media_type: str, tmdb_id: int | None, state: dict, season_number: int | None = None):
    if not tmdb_id:
        return

    key_media_type = MediaType.TV if media_type in (MediaType.TV, WatchEntryMediaType.EPISODE) else media_type
    key = (key_media_type, tmdb_id)
    if key not in state['metadata_checked']:
        if _has_tmdb_metadata(media_type, tmdb_id):
            state['metadata_hits'] += 1
        else:
            if _ensure_tmdb_metadata(media_type, tmdb_id):
                state['metadata_fetches'] += 1
            else:
                state['metadata_errors'] += 1
        state['metadata_checked'].add(key)

    if media_type == WatchEntryMediaType.EPISODE:
        _ensure_tv_season_metadata(tmdb_id, season_number, state)


def _is_supported_zip_file(file_name: str) -> bool:
    lower = file_name.lower()
    return (
        lower.startswith(('watched-history-', 'watched-movies-', 'ratings-movies-'))
        or lower == 'watched-shows.json'
        or lower == 'lists-watchlist.json'
        or lower == 'ratings-shows.json'
        or lower in ('hidden-progress-watched.json', 'hidden-progress-watched-reset.json')
    )


def _watch_entry_key(media_type: str, tmdb_id: int, season_number: int | None = None, episode_number: int | None = None):
    return (media_type, int(tmdb_id), season_number, episode_number)


def _watchlist_key(media_type: str, tmdb_id: int):
    return (media_type, int(tmdb_id))


def _rating_key(media_type: str, tmdb_id: int):
    return (media_type, int(tmdb_id))


def _import_watch_entry_by_mode(
    user,
    media_type: str,
    tmdb_id: int,
    watched_at,
    import_mode: str,
    season_number: int | None = None,
    episode_number: int | None = None,
) -> bool:
    existing = WatchEntry.objects.filter(
        user=user,
        media_type=media_type,
        tmdb_id=tmdb_id,
        season_number=season_number,
        episode_number=episode_number,
    ).first()
    if existing and import_mode == DataImportMode.NEW_ITEMS:
        return False

    result = _upsert_watch_entry(
        user,
        media_type,
        tmdb_id,
        watched_at,
        season_number=season_number,
        episode_number=episode_number,
    )
    return result in ('created', 'updated')


def _import_watchlist_by_mode(user, media_type: str, tmdb_id: int, notes: str, import_mode: str) -> bool:
    existing = Watchlist.objects.filter(user=user, media_type=media_type, tmdb_id=tmdb_id).first()
    if existing:
        if import_mode == DataImportMode.NEW_ITEMS:
            return False
        if existing.notes != notes:
            existing.notes = notes
            existing.save(update_fields=['notes'])
            return True
        return False

    Watchlist.objects.create(user=user, media_type=media_type, tmdb_id=tmdb_id, notes=notes)
    return True


def _import_rating_by_mode(user, media_type: str, tmdb_id: int, score: int, import_mode: str) -> bool:
    existing = Rating.objects.filter(user=user, media_type=media_type, tmdb_id=tmdb_id).first()
    if existing:
        if import_mode == DataImportMode.NEW_ITEMS:
            return False
        if existing.score != score:
            existing.score = score
            existing.save(update_fields=['score'])
            return True
        return False

    Rating.objects.create(user=user, media_type=media_type, tmdb_id=tmdb_id, score=score)
    return True


def _handle_watched_history_record(record: dict, user, state: dict) -> bool:
    item_type = (record.get('type') or '').lower()
    watched_at = _parse_watched_at(record.get('watched_at'))

    if item_type == MediaType.MOVIE:
        tmdb_id = _safe_int((record.get('movie') or {}).get('ids', {}).get('tmdb'))
        if not tmdb_id:
            return False
        _ensure_tmdb_metadata_for_import_item(MediaType.MOVIE, tmdb_id, state)
        _upsert_watch_entry(user, MediaType.MOVIE, tmdb_id, watched_at)
        return True

    if item_type == WatchEntryMediaType.EPISODE:
        show = record.get('show') or {}
        episode = record.get('episode') or {}
        tmdb_id = _safe_int(show.get('ids', {}).get('tmdb'))
        season_number = _safe_int(episode.get('season'))
        episode_number = _safe_int(episode.get('number'))
        if not tmdb_id or season_number is None or episode_number is None:
            return False
        _ensure_tmdb_metadata_for_import_item(WatchEntryMediaType.EPISODE, tmdb_id, state, season_number=season_number)
        _upsert_watch_entry(
            user,
            WatchEntryMediaType.EPISODE,
            tmdb_id,
            watched_at,
            season_number=season_number,
            episode_number=episode_number,
        )
        return True

    return False


def _handle_watched_movies_record(record: dict, user, state: dict) -> bool:
    tmdb_id = _safe_int((record.get('movie') or {}).get('ids', {}).get('tmdb'))
    if not tmdb_id:
        return False
    watched_at = _parse_watched_at(record.get('last_watched_at') or record.get('last_updated_at'))
    _ensure_tmdb_metadata_for_import_item(MediaType.MOVIE, tmdb_id, state)
    _upsert_watch_entry(user, MediaType.MOVIE, tmdb_id, watched_at)
    return True


def _handle_watchlist_record(record: dict, user, state: dict) -> bool:
    item_type = (record.get('type') or '').lower()
    if item_type == MediaType.MOVIE:
        media_type = MediaType.MOVIE
        item = record.get('movie') or {}
    elif item_type == 'show':
        media_type = MediaType.TV
        item = record.get('show') or {}
    else:
        return False

    tmdb_id = _safe_int(item.get('ids', {}).get('tmdb'))
    if not tmdb_id:
        return False

    _ensure_tmdb_metadata_for_import_item(media_type, tmdb_id, state)
    Watchlist.objects.update_or_create(
        user=user,
        media_type=media_type,
        tmdb_id=tmdb_id,
        defaults={'notes': ''},
    )
    return True


def _handle_rating_record(record: dict, user, state: dict) -> bool:
    item_type = (record.get('type') or '').lower()
    if item_type == MediaType.MOVIE:
        media_type = MediaType.MOVIE
        item = record.get('movie') or {}
    elif item_type == 'show':
        media_type = MediaType.TV
        item = record.get('show') or {}
    else:
        return False

    tmdb_id = _safe_int(item.get('ids', {}).get('tmdb'))
    score = _safe_int(record.get('rating'))
    if not tmdb_id or not score:
        return False

    _ensure_tmdb_metadata_for_import_item(media_type, tmdb_id, state)
    Rating.objects.update_or_create(
        user=user,
        media_type=media_type,
        tmdb_id=tmdb_id,
        defaults={'score': score},
    )
    return True


def _handle_watched_show_record(record: dict, state: dict) -> bool:
    tmdb_id = _safe_int((record.get('show') or {}).get('ids', {}).get('tmdb'))
    if not tmdb_id:
        return False
    _ensure_tmdb_metadata_for_import_item(MediaType.TV, tmdb_id, state)
    return True


def _mark_show_dropped(user, tmdb_id: int):
    dropped_at = timezone.now()
    dropped_entry = WatchEntry.objects.filter(
        user=user,
        media_type=WatchEntryMediaType.EPISODE,
        tmdb_id=tmdb_id,
        season_number__isnull=True,
        episode_number__isnull=True,
        status=WatchEntryStatus.DROPPED,
    ).order_by('-id').first()

    if dropped_entry:
        dropped_entry.watched_at = dropped_at
        dropped_entry.save(update_fields=['watched_at'])
    else:
        WatchEntry.objects.create(
            user=user,
            media_type=WatchEntryMediaType.EPISODE,
            tmdb_id=tmdb_id,
            season_number=None,
            episode_number=None,
            status=WatchEntryStatus.DROPPED,
            watched_at=dropped_at,
        )


def _handle_hidden_progress_record(record: dict, user, state: dict) -> bool:
    item_type = (record.get('type') or '').lower()
    if item_type != 'show':
        return False
    tmdb_id = _safe_int((record.get('show') or {}).get('ids', {}).get('tmdb'))
    if not tmdb_id:
        return False

    _ensure_tmdb_metadata_for_import_item(MediaType.TV, tmdb_id, state)
    _mark_show_dropped(user, tmdb_id)
    return True


def _zip_collection_from_file(file_name: str) -> str | None:
    lower = file_name.lower()
    if lower.startswith(('watched-history-', 'watched-movies-')):
        return 'watch_history'
    if lower == 'lists-watchlist.json':
        return 'watchlist'
    if lower.startswith('ratings-movies-') or lower == 'ratings-shows.json':
        return 'ratings'
    if lower in ('hidden-progress-watched.json', 'hidden-progress-watched-reset.json'):
        return 'watch_history'
    return None


def _normalize_zip_records(file_name: str, parsed):
    lower = file_name.lower()
    if lower == 'lists-watchlist.json' and isinstance(parsed, dict):
        items = parsed.get('items')
        if isinstance(items, list):
            return items
    return parsed if isinstance(parsed, list) else [parsed]


def _analyze_trakt_zip(job: DataTransferJob, content: bytes) -> dict:
    report: dict[str, Any] = _default_import_report()
    report['summary'] = {
        'watch_history': 0,
        'watchlist': 0,
        'ratings': 0,
    }

    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        file_names = sorted((name for name in archive.namelist() if name.lower().endswith('.json')), key=_zip_json_sort_key)

        for name in file_names:
            file_name = name.rsplit('/', 1)[-1]
            file_report: dict[str, Any] = {
                'file': file_name,
                'status': 'processed',
                'records_seen': 0,
                'records_imported': 0,
                'records_skipped': 0,
                'error': '',
            }
            report['files_processed'] += 1

            if not _is_supported_zip_file(file_name):
                report['unsupported_files'] += 1

            try:
                with archive.open(name) as file_obj:
                    raw = file_obj.read().decode('utf-8')
                parsed = json.loads(raw)
            except Exception as exc:
                report['files_failed'] += 1
                file_report['status'] = DataTransferStatus.FAILED
                file_report['error'] = str(exc)
                report['files'].append(file_report)
                continue

            records = _normalize_zip_records(file_name, parsed)
            category = _zip_collection_from_file(file_name)
            for record in records:
                file_report['records_seen'] += 1
                report['records_seen'] += 1
                if isinstance(record, dict) and category:
                    report['records_imported'] += 1
                    file_report['records_imported'] += 1
                    report['summary'][category] += 1
                else:
                    report['records_skipped'] += 1
                    file_report['records_skipped'] += 1
                    if isinstance(record, dict) and not category:
                        report['unsupported_records'] += 1

            report['files'].append(file_report)

    report['metadata_hits'] = 0
    report['metadata_fetches'] = 0
    report['metadata_errors'] = 0
    report['total_items'] = report['records_seen']
    return report


def _apply_zip_record_by_mode(
    file_name: str,
    record,
    user,
    state: dict,
    report: dict,
    import_mode: str,
    imported_keys: dict,
):
    lower = file_name.lower()
    if not isinstance(record, dict):
        report['records_skipped'] += 1
        return

    if lower.startswith('watched-history-'):
        item_type = (record.get('type') or '').lower()
        watched_at = _parse_watched_at(record.get('watched_at'))
        if item_type == MediaType.MOVIE:
            tmdb_id = _safe_int((record.get('movie') or {}).get('ids', {}).get('tmdb'))
            if not tmdb_id:
                report['records_skipped'] += 1
                return
            _ensure_tmdb_metadata_for_import_item(MediaType.MOVIE, tmdb_id, state)
            imported_keys['watch_entries'].add(_watch_entry_key(MediaType.MOVIE, tmdb_id))
            _import_watch_entry_by_mode(user, MediaType.MOVIE, tmdb_id, watched_at, import_mode)
            report['records_imported'] += 1
            return

        if item_type == WatchEntryMediaType.EPISODE:
            show = record.get('show') or {}
            episode = record.get('episode') or {}
            tmdb_id = _safe_int(show.get('ids', {}).get('tmdb'))
            season_number = _safe_int(episode.get('season'))
            episode_number = _safe_int(episode.get('number'))
            if not tmdb_id or season_number is None or episode_number is None:
                report['records_skipped'] += 1
                return
            _ensure_tmdb_metadata_for_import_item(WatchEntryMediaType.EPISODE, tmdb_id, state, season_number=season_number)
            imported_keys['watch_entries'].add(_watch_entry_key(WatchEntryMediaType.EPISODE, tmdb_id, season_number, episode_number))
            _import_watch_entry_by_mode(
                user,
                WatchEntryMediaType.EPISODE,
                tmdb_id,
                watched_at,
                import_mode,
                season_number=season_number,
                episode_number=episode_number,
            )
            report['records_imported'] += 1
            return

        report['records_skipped'] += 1
        return

    if lower.startswith('watched-movies-'):
        tmdb_id = _safe_int((record.get('movie') or {}).get('ids', {}).get('tmdb'))
        if not tmdb_id:
            report['records_skipped'] += 1
            return
        watched_at = _parse_watched_at(record.get('last_watched_at') or record.get('last_updated_at'))
        _ensure_tmdb_metadata_for_import_item(MediaType.MOVIE, tmdb_id, state)
        imported_keys['watch_entries'].add(_watch_entry_key(MediaType.MOVIE, tmdb_id))
        _import_watch_entry_by_mode(user, MediaType.MOVIE, tmdb_id, watched_at, import_mode)
        report['records_imported'] += 1
        return

    if lower == 'lists-watchlist.json':
        item_type = (record.get('type') or '').lower()
        if item_type == MediaType.MOVIE:
            media_type = MediaType.MOVIE
            item = record.get('movie') or {}
        elif item_type == 'show':
            media_type = MediaType.TV
            item = record.get('show') or {}
        else:
            report['records_skipped'] += 1
            return
        tmdb_id = _safe_int(item.get('ids', {}).get('tmdb'))
        if not tmdb_id:
            report['records_skipped'] += 1
            return
        _ensure_tmdb_metadata_for_import_item(media_type, tmdb_id, state)
        imported_keys['watchlist'].add(_watchlist_key(media_type, tmdb_id))
        _import_watchlist_by_mode(user, media_type, tmdb_id, '', import_mode)
        report['records_imported'] += 1
        return

    if lower.startswith('ratings-movies-') or lower == 'ratings-shows.json':
        item_type = (record.get('type') or '').lower()
        if item_type == MediaType.MOVIE:
            media_type = MediaType.MOVIE
            item = record.get('movie') or {}
        elif item_type == 'show':
            media_type = MediaType.TV
            item = record.get('show') or {}
        else:
            report['records_skipped'] += 1
            return
        tmdb_id = _safe_int(item.get('ids', {}).get('tmdb'))
        score = _safe_int(record.get('rating'))
        if not tmdb_id or not score:
            report['records_skipped'] += 1
            return
        _ensure_tmdb_metadata_for_import_item(media_type, tmdb_id, state)
        imported_keys['ratings'].add(_rating_key(media_type, tmdb_id))
        _import_rating_by_mode(user, media_type, tmdb_id, score, import_mode)
        report['records_imported'] += 1
        return

    if lower in ('hidden-progress-watched.json', 'hidden-progress-watched-reset.json'):
        item_type = (record.get('type') or '').lower()
        if item_type != 'show':
            report['records_skipped'] += 1
            return
        tmdb_id = _safe_int((record.get('show') or {}).get('ids', {}).get('tmdb'))
        if not tmdb_id:
            report['records_skipped'] += 1
            return
        _ensure_tmdb_metadata_for_import_item(MediaType.TV, tmdb_id, state)
        imported_keys['watch_entries'].add(_watch_entry_key(WatchEntryMediaType.EPISODE, tmdb_id, None, None))
        if import_mode != DataImportMode.NEW_ITEMS or not WatchEntry.objects.filter(
            user=user,
            media_type=WatchEntryMediaType.EPISODE,
            tmdb_id=tmdb_id,
            season_number__isnull=True,
            episode_number__isnull=True,
            status=WatchEntryStatus.DROPPED,
        ).exists():
            _mark_show_dropped(user, tmdb_id)
        report['records_imported'] += 1
        return

    if lower == 'watched-shows.json':
        _handle_watched_show_record(record, state)
        report['records_imported'] += 1
        return

    report['unsupported_records'] += 1
    report['records_skipped'] += 1


def _apply_mirror_deletions(job: DataTransferJob, imported_keys: dict, collections_present: set[str]):
    if 'watch_history' in collections_present:
        delete_ids = []
        for entry in WatchEntry.objects.filter(
            user=job.user,
            status__in=[WatchEntryStatus.WATCHED, WatchEntryStatus.DROPPED],
        ):
            key = _watch_entry_key(entry.media_type, entry.tmdb_id, entry.season_number, entry.episode_number)
            if key not in imported_keys['watch_entries']:
                delete_ids.append(entry.id)
        if delete_ids:
            WatchEntry.objects.filter(id__in=delete_ids).delete()

    if 'watchlist' in collections_present:
        delete_ids = []
        for item in Watchlist.objects.filter(user=job.user):
            key = _watchlist_key(item.media_type, item.tmdb_id)
            if key not in imported_keys['watchlist']:
                delete_ids.append(item.id)
        if delete_ids:
            Watchlist.objects.filter(id__in=delete_ids).delete()

    if 'ratings' in collections_present:
        delete_ids = []
        for rating_item in Rating.objects.filter(user=job.user):
            key = _rating_key(rating_item.media_type, rating_item.tmdb_id)
            if key not in imported_keys['ratings']:
                delete_ids.append(rating_item.id)
        if delete_ids:
            Rating.objects.filter(id__in=delete_ids).delete()


def _apply_trakt_zip(job: DataTransferJob, content: bytes, import_mode: str):
    report: dict[str, Any] = _default_import_report()
    state = {
        'metadata_checked': set(),
        'season_checked': set(),
        'metadata_hits': 0,
        'metadata_fetches': 0,
        'metadata_errors': 0,
    }
    imported_keys: dict[str, set[tuple[object, ...]]] = {
        'watch_entries': set(),
        'watchlist': set(),
        'ratings': set(),
    }
    collections_present = set()

    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        file_names = sorted((name for name in archive.namelist() if name.lower().endswith('.json')), key=_zip_json_sort_key)

        for name in file_names:
            file_name = name.rsplit('/', 1)[-1]
            file_report: dict[str, Any] = {
                'file': file_name,
                'status': 'processed',
                'records_seen': 0,
                'records_imported': 0,
                'records_skipped': 0,
                'error': '',
            }
            report['files_processed'] += 1
            if not _is_supported_zip_file(file_name):
                report['unsupported_files'] += 1

            try:
                with archive.open(name) as file_obj:
                    raw = file_obj.read().decode('utf-8')
                parsed = json.loads(raw)
            except Exception as exc:
                report['files_failed'] += 1
                file_report['status'] = DataTransferStatus.FAILED
                file_report['error'] = str(exc)
                report['files'].append(file_report)
                continue

            records = _normalize_zip_records(file_name, parsed)
            category = _zip_collection_from_file(file_name)
            if category:
                collections_present.add(category)
            for record in records:
                file_report['records_seen'] += 1
                report['records_seen'] += 1
                before_imported = report['records_imported']
                before_skipped = report['records_skipped']

                _apply_zip_record_by_mode(file_name, record, job.user, state, report, import_mode, imported_keys)

                if report['records_imported'] > before_imported:
                    file_report['records_imported'] += 1
                if report['records_skipped'] > before_skipped:
                    file_report['records_skipped'] += 1

                job.processed_items += 1
                _update_job_progress(job)

            report['files'].append(file_report)

    if import_mode == DataImportMode.MIRROR_IMPORTED_SET:
        _apply_mirror_deletions(job, imported_keys, collections_present)

    report['metadata_hits'] = state['metadata_hits']
    report['metadata_fetches'] = state['metadata_fetches']
    report['metadata_errors'] = state['metadata_errors']
    report['summary'] = {
        'watch_history': len(imported_keys['watch_entries']),
        'watchlist': len(imported_keys['watchlist']),
        'ratings': len(imported_keys['ratings']),
    }
    report['total_items'] = job.total_items
    job.metadata = report
    job.save(update_fields=['total_items', 'processed_items', 'metadata', 'updated_at'])


def _ensure_tmdb_metadata(media_type: str, tmdb_id: int | None) -> bool:
    if not tmdb_id:
        return False

    try:
        if media_type == MediaType.MOVIE:
            tmdb.sync_movie(int(tmdb_id))
        elif media_type in (MediaType.TV, WatchEntryMediaType.EPISODE):
            tmdb.sync_tv_show(int(tmdb_id))
        else:
            return False
        return True
    except Exception as exc:
        logger.warning('Failed metadata sync for %s %s: %s', media_type, tmdb_id, exc)
        return False


def _has_tmdb_metadata(media_type: str, tmdb_id: int | None) -> bool:
    if not tmdb_id:
        return False

    if media_type == MediaType.MOVIE:
        return Movie.objects.filter(tmdb_id=int(tmdb_id)).exists()

    if media_type in (MediaType.TV, WatchEntryMediaType.EPISODE):
        return TVShow.objects.filter(tmdb_id=int(tmdb_id)).exists()

    return False

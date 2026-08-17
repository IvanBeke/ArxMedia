import csv
import io
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from ...choices import (
    DataImportMode,
    DataTransferFormat,
    MediaType,
    TvShowStatus,
    WatchEntryMediaType,
    WatchEntryStatus,
)
from ...models import DataTransferJob
from ...status_sync import refresh_show_and_season_statuses
from ..shared import (
    _apply_mirror_deletions,
    _ensure_tmdb_metadata_for_import_item,
    _import_rating_by_mode,
    _import_tv_status_by_mode,
    _import_watch_entry_status_by_mode,
    _import_watchlist_by_mode,
    _parse_watched_at,
    _rating_key,
    _safe_int,
    _update_job_progress,
    _watch_entry_key,
    _watchlist_key,
)

YAMTRACK_ALLOWED_MEDIA_TYPES = {'movie', 'tv', 'season', 'episode'}
YAMTRACK_ALLOWED_STATUSES = {'Completed', 'In progress', 'Planning', 'Paused', 'Dropped', ''}


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


def _default_yamtrack_report() -> dict:
    return {
        'format': DataTransferFormat.CSV,
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


def analyze_yamtrack_csv(content: bytes) -> dict:
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


def apply_yamtrack_csv_import(job: DataTransferJob, content: bytes, import_mode: str):
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

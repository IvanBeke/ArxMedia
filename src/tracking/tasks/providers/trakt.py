import io
import json
import re
import zipfile
from typing import Any

from ...choices import DataImportMode, DataTransferFormat, MediaType, WatchEntryMediaType, WatchEntryStatus
from ...models import DataTransferJob, WatchEntry
from ..shared import (
    _apply_mirror_deletions,
    _ensure_tmdb_metadata_for_import_item,
    _import_rating_by_mode,
    _import_watch_entry_by_mode,
    _import_watchlist_by_mode,
    _mark_show_dropped,
    _parse_watched_at,
    _rating_key,
    _safe_int,
    _update_job_progress,
    _watch_entry_key,
    _watchlist_key,
)


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


def _is_supported_zip_file(file_name: str) -> bool:
    lower = file_name.lower()
    return (
        lower.startswith(('watched-history-', 'watched-movies-', 'ratings-movies-'))
        or lower == 'watched-shows.json'
        or lower == 'lists-watchlist.json'
        or lower == 'ratings-shows.json'
        or lower in ('hidden-progress-watched.json', 'hidden-progress-watched-reset.json')
    )


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


def _handle_watched_show_record(record: dict, state: dict) -> bool:
    tmdb_id = _safe_int((record.get('show') or {}).get('ids', {}).get('tmdb'))
    if not tmdb_id:
        return False
    _ensure_tmdb_metadata_for_import_item(MediaType.TV, tmdb_id, state)
    return True


def analyze_trakt_zip(content: bytes) -> dict:
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
                file_report['status'] = 'failed'
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


def apply_trakt_zip_import(job: DataTransferJob, content: bytes, import_mode: str):
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
                file_report['status'] = 'failed'
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

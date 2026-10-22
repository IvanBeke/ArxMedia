"""Trakt zip import provider: pure parsing only (no DB/TMDB access)."""

import json
import re
from typing import Any

from ...choices import DataTransferFormat, MediaType, TvShowStatus, WatchEntryMediaType
from ...import_config import open_import_zip
from ...import_metadata import _parse_watched_at, _safe_int
from ...import_records import (
    RATINGS_COLLECTION,
    WATCH_HISTORY_COLLECTION,
    WATCHLIST_COLLECTION,
    ParsedImport,
    RatingRecord,
    StatusRecord,
    WatchEntryRecord,
    add_import_warning,
)


def _zip_json_sort_key(name: str):
    file_name = name.rsplit('/', 1)[-1].lower()
    match = re.match(r'^(.*?)-(\d+)\.json$', file_name)
    if match:
        return match.group(1), int(match.group(2)), file_name
    return file_name, 0, file_name


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
        return WATCH_HISTORY_COLLECTION
    if lower == 'lists-watchlist.json':
        return WATCHLIST_COLLECTION
    if lower.startswith('ratings-movies-') or lower == 'ratings-shows.json':
        return RATINGS_COLLECTION
    if lower in ('hidden-progress-watched.json', 'hidden-progress-watched-reset.json'):
        return WATCH_HISTORY_COLLECTION
    return None


def _normalize_zip_records(file_name: str, parsed):
    lower = file_name.lower()
    if lower == 'lists-watchlist.json' and isinstance(parsed, dict):
        items = parsed.get('items')
        if isinstance(items, list):
            return items
    return parsed if isinstance(parsed, list) else [parsed]


def _media_from_record(record: dict) -> tuple[str, int]:
    item_type = (record.get('type') or '').lower()
    if item_type == MediaType.MOVIE:
        item = record.get('movie') or {}
        media_type = MediaType.MOVIE
    elif item_type == 'show':
        item = record.get('show') or {}
        media_type = MediaType.TV
    else:
        return '', 0
    tmdb_id = _safe_int((item or {}).get('ids', {}).get('tmdb'))
    return media_type, tmdb_id or 0


class _TraktStats:
    """Mutable state threaded through the per-file record handling."""

    def __init__(self) -> None:
        self.records: list[WatchEntryRecord | StatusRecord | RatingRecord] = []
        self.invalid_count = 0
        self.collections: set[str] = set()
        self.files_report: list[dict] = []
        self.files_processed = 0
        self.files_failed = 0
        self.unsupported_files = 0
        self.unsupported_records = 0
        self.metadata_only_count = 0
        self.show_ids: set[int] = set()
        self.warnings: list[dict] = []


def _trakt_ctx(record: dict, file_name: str, file_lower: str, seen: int) -> dict[str, Any]:
    return {'file': file_name, 'file_lower': file_lower, 'record': record, 'seen': seen}


def _trakt_invalid_record(stats: _TraktStats, ctx: dict[str, Any], code: str, message: str) -> None:
    add_import_warning(stats.warnings, code, message, {'kind': 'zip_record', 'file': ctx['file'], 'record': ctx['seen']})


def _append_history_movie_record(stats: _TraktStats, ctx: dict[str, Any]) -> bool:
    tmdb_id = _safe_int((ctx['record'].get('movie') or {}).get('ids', {}).get('tmdb'))
    if not tmdb_id:
        return False
    stats.records.append(
        WatchEntryRecord(
            media_type=WatchEntryMediaType.MOVIE,
            tmdb_id=tmdb_id,
            watched_at=_parse_watched_at(ctx['record'].get('watched_at')),
            origin=ctx['file'],
        )
    )
    return True


def _append_history_episode_record(stats: _TraktStats, ctx: dict[str, Any]) -> bool:
    show = ctx['record'].get('show') or {}
    episode = ctx['record'].get('episode') or {}
    tmdb_id = _safe_int(show.get('ids', {}).get('tmdb'))
    season_number = _safe_int(episode.get('season'))
    episode_number = _safe_int(episode.get('number'))
    if not tmdb_id or season_number is None or episode_number is None:
        return False
    stats.records.append(
        WatchEntryRecord(
            media_type=WatchEntryMediaType.EPISODE,
            tmdb_id=tmdb_id,
            watched_at=_parse_watched_at(ctx['record'].get('watched_at')),
            season_number=season_number,
            episode_number=episode_number,
            origin=ctx['file'],
        )
    )
    return True


def _invalid_history(stats: _TraktStats, ctx: dict[str, Any]) -> None:
    stats.invalid_count += 1
    _trakt_invalid_record(
        stats, ctx, 'invalid_watch_history',
        'The watch history record is missing a valid TMDB ID or episode number.',
    )


def _history_movie_entry(stats: _TraktStats, ctx: dict[str, Any]) -> None:
    if not _append_history_movie_record(stats, ctx):
        _invalid_history(stats, ctx)


def _history_episode_entry(stats: _TraktStats, ctx: dict[str, Any]) -> None:
    if not _append_history_episode_record(stats, ctx):
        _invalid_history(stats, ctx)


def _handle_trakt_watch_history(stats: _TraktStats, ctx: dict[str, Any]) -> None:
    item_type = (ctx['record'].get('type') or '').lower()
    if item_type == MediaType.MOVIE:
        _history_movie_entry(stats, ctx)
        return
    if item_type == WatchEntryMediaType.EPISODE:
        _history_episode_entry(stats, ctx)
        return
    _invalid_history(stats, ctx)


def _handle_trakt_watched_movies(stats: _TraktStats, ctx: dict[str, Any]) -> None:
    tmdb_id = _safe_int((ctx['record'].get('movie') or {}).get('ids', {}).get('tmdb'))
    if not tmdb_id:
        stats.invalid_count += 1
        _trakt_invalid_record(stats, ctx, 'missing_tmdb_id', 'The watched movie record does not contain a TMDB ID.')
        return
    stats.records.append(
        WatchEntryRecord(
            media_type=WatchEntryMediaType.MOVIE,
            tmdb_id=tmdb_id,
            watched_at=_parse_watched_at(ctx['record'].get('last_watched_at') or ctx['record'].get('last_updated_at')),
            origin=ctx['file'],
        )
    )


def _handle_trakt_watchlist(stats: _TraktStats, ctx: dict[str, Any]) -> None:
    media_type, tmdb_id = _media_from_record(ctx['record'])
    if not tmdb_id:
        stats.invalid_count += 1
        _trakt_invalid_record(stats, ctx, 'missing_tmdb_id', 'The watchlist record does not contain a TMDB ID.')
        return
    stats.records.append(StatusRecord(
        media_type=media_type, tmdb_id=tmdb_id,
        status=TvShowStatus.PLAN_TO_WATCH, origin=ctx['file'],
    ))


def _handle_trakt_ratings(stats: _TraktStats, ctx: dict[str, Any]) -> None:
    media_type, tmdb_id = _media_from_record(ctx['record'])
    score = _safe_int(ctx['record'].get('rating'))
    rated_at = _parse_watched_at(ctx['record'].get('rated_at'))
    if not tmdb_id or not score or rated_at is None:
        stats.invalid_count += 1
        _trakt_invalid_record(
            stats, ctx, 'invalid_rating',
            'The rating record is missing a TMDB ID, valid rating, or valid rated_at.',
        )
        return
    stats.records.append(RatingRecord(
        media_type=media_type, tmdb_id=tmdb_id, score=score, rated_at=rated_at, origin=ctx['file'],
    ))


def _handle_trakt_hidden_progress(stats: _TraktStats, ctx: dict[str, Any]) -> None:
    _, tmdb_id = _media_from_record(ctx['record'])
    if not tmdb_id:
        stats.invalid_count += 1
        _trakt_invalid_record(stats, ctx, 'missing_tmdb_id', 'The hidden progress record does not contain a TMDB ID.')
        return
    stats.records.append(StatusRecord(
        media_type=MediaType.TV, tmdb_id=tmdb_id,
        status=TvShowStatus.DROPPED,
        status_at=_parse_watched_at(ctx['record'].get('hidden_at')), origin=ctx['file'],
    ))


def _handle_trakt_watched_shows(stats: _TraktStats, ctx: dict[str, Any]) -> None:
    # Show-level history entries carry no per-episode data here;
    # they only guarantee show metadata exists.
    tmdb_id = _safe_int((ctx['record'].get('show') or {}).get('ids', {}).get('tmdb'))
    if not tmdb_id:
        stats.invalid_count += 1
        _trakt_invalid_record(stats, ctx, 'missing_tmdb_id', 'The watched show record does not contain a TMDB ID.')
        return
    stats.metadata_only_count += 1
    stats.show_ids.add(tmdb_id)


_EXACT_FILE_HANDLERS = {
    'lists-watchlist.json': _handle_trakt_watchlist,
    'ratings-shows.json': _handle_trakt_ratings,
    'hidden-progress-watched.json': _handle_trakt_hidden_progress,
    'hidden-progress-watched-reset.json': _handle_trakt_hidden_progress,
    'watched-shows.json': _handle_trakt_watched_shows,
}


def _prefix_trakt_handler(file_lower: str):
    if file_lower.startswith('watched-history-'):
        return _handle_trakt_watch_history
    if file_lower.startswith('watched-movies-'):
        return _handle_trakt_watched_movies
    if file_lower.startswith('ratings-movies-'):
        return _handle_trakt_ratings
    return None


def _trakt_handler_for(file_lower: str):
    """Pick the record handler by file name; ``None`` means unsupported."""
    handler = _EXACT_FILE_HANDLERS.get(file_lower)
    if handler is not None:
        return handler
    return _prefix_trakt_handler(file_lower)


def _consume_trakt_record(stats: _TraktStats, file_report: dict, record, file_name: str, file_lower: str) -> None:
    handler = _trakt_handler_for(file_lower)
    if not isinstance(record, dict):
        stats.invalid_count += 1
        add_import_warning(
            stats.warnings, 'invalid_record', 'The record is not a JSON object.',
            {'kind': 'zip_record', 'file': file_name, 'record': file_report['records_seen']},
        )
        return
    ctx = _trakt_ctx(record, file_name, file_lower, file_report['records_seen'])
    if handler is None:
        stats.unsupported_records += 1
        stats.invalid_count += 1
        _trakt_invalid_record(stats, ctx, 'unsupported_record', 'This file or record is not supported by the Trakt importer.')
        return
    handler(stats, ctx)


def _read_trakt_file(archive, name: str):
    with archive.open(name) as file_obj:
        raw = file_obj.read().decode('utf-8')
    return json.loads(raw)


def _parse_trakt_file(archive, name: str, stats: _TraktStats) -> None:
    file_name = name.rsplit('/', 1)[-1]
    file_report: dict = {'file': file_name, 'status': 'processed', 'records_seen': 0, 'error': ''}
    stats.files_processed += 1
    if not _is_supported_zip_file(file_name):
        stats.unsupported_files += 1

    try:
        parsed = _read_trakt_file(archive, name)
    except Exception as exc:
        stats.files_failed += 1
        file_report['status'] = 'failed'
        file_report['error'] = str(exc)
        add_import_warning(stats.warnings, 'file_parse_error', str(exc), {'kind': 'zip_file', 'file': file_name})
        stats.files_report.append(file_report)
        return

    category = _zip_collection_from_file(file_name)
    if category:
        stats.collections.add(category)
    file_lower = file_name.lower()

    for record in _normalize_zip_records(file_name, parsed):
        file_report['records_seen'] += 1
        _consume_trakt_record(stats, file_report, record, file_name, file_lower)

    stats.files_report.append(file_report)


def _classify_trakt_record(summary: dict, record) -> None:
    if isinstance(record, WatchEntryRecord):
        summary['watch_history'] += 1
    elif isinstance(record, StatusRecord) and record.status == TvShowStatus.PLAN_TO_WATCH:
        summary['watchlist'] += 1
    elif isinstance(record, RatingRecord):
        summary['ratings'] += 1


def _trakt_summary(records: list) -> dict:
    summary = {'watch_history': 0, 'watchlist': 0, 'ratings': 0}
    for record in records:
        _classify_trakt_record(summary, record)
    return summary


def _trakt_report(stats: _TraktStats) -> dict:
    records_seen = sum(f['records_seen'] for f in stats.files_report)
    return {
        'format': DataTransferFormat.ZIP,
        'files_processed': stats.files_processed,
        'files_failed': stats.files_failed,
        'unsupported_files': stats.unsupported_files,
        'unsupported_records': stats.unsupported_records,
        'metadata_only_shows': stats.metadata_only_count,
        'records_seen': records_seen,
        'invalid_count': stats.invalid_count,
        'summary': _trakt_summary(stats.records),
        'total_items': records_seen,
        'files': stats.files_report,
        'warnings': stats.warnings,
        'warnings_total': stats.invalid_count,
        'warnings_truncated': stats.invalid_count > len(stats.warnings),
    }


def parse_trakt_zip(content: bytes) -> ParsedImport:
    stats = _TraktStats()

    with open_import_zip(content) as archive:
        file_names = sorted((name for name in archive.namelist() if name.lower().endswith('.json')), key=_zip_json_sort_key)
        for name in file_names:
            _parse_trakt_file(archive, name, stats)

    return ParsedImport(
        records=tuple(stats.records),
        collections_present=frozenset(stats.collections),
        invalid_count=stats.invalid_count,
        report=_trakt_report(stats),
        prefetch_only_ids={MediaType.TV: frozenset(stats.show_ids)},
    )


def analyze_trakt_zip(content: bytes) -> dict:
    parsed = parse_trakt_zip(content)
    report = dict(parsed.report)
    report.update(
        {
            'records_imported': 0,
            'records_skipped': parsed.report['records_seen'],
            'metadata_hits': 0,
            'metadata_fetches': 0,
            'metadata_errors': 0,
        }
    )
    return report

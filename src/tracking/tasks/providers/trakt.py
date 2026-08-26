"""Trakt zip import provider: pure parsing only (no DB/TMDB access)."""

import io
import json
import re
import zipfile

from ...choices import DataTransferFormat, MediaType, TvShowStatus, WatchEntryMediaType
from ...import_metadata import _parse_watched_at, _safe_int
from ...import_records import (
    RATINGS_COLLECTION,
    WATCH_HISTORY_COLLECTION,
    WATCHLIST_COLLECTION,
    ParsedImport,
    RatingRecord,
    StatusRecord,
    WatchEntryRecord,
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


def parse_trakt_zip(content: bytes) -> ParsedImport:
    records: list[WatchEntryRecord | StatusRecord | RatingRecord] = []
    invalid_count = 0
    collections: set[str] = set()
    files_report: list[dict] = []
    files_processed = 0
    files_failed = 0
    unsupported_files = 0
    unsupported_records = 0
    metadata_only_count = 0
    show_ids: set[int] = set()

    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        file_names = sorted((name for name in archive.namelist() if name.lower().endswith('.json')), key=_zip_json_sort_key)

        for name in file_names:
            file_name = name.rsplit('/', 1)[-1]
            file_report: dict = {'file': file_name, 'status': 'processed', 'records_seen': 0, 'error': ''}
            files_processed += 1

            if not _is_supported_zip_file(file_name):
                unsupported_files += 1

            try:
                with archive.open(name) as file_obj:
                    raw = file_obj.read().decode('utf-8')
                parsed = json.loads(raw)
            except Exception as exc:
                files_failed += 1
                file_report['status'] = 'failed'
                file_report['error'] = str(exc)
                files_report.append(file_report)
                continue

            records_in_file = _normalize_zip_records(file_name, parsed)
            category = _zip_collection_from_file(file_name)
            if category:
                collections.add(category)
            lower = file_name.lower()

            for record in records_in_file:
                file_report['records_seen'] += 1
                if not isinstance(record, dict):
                    invalid_count += 1
                    continue

                if lower.startswith('watched-history-'):
                    item_type = (record.get('type') or '').lower()
                    watched_at = _parse_watched_at(record.get('watched_at'))
                    if item_type == MediaType.MOVIE:
                        tmdb_id = _safe_int((record.get('movie') or {}).get('ids', {}).get('tmdb'))
                        if tmdb_id:
                            records.append(WatchEntryRecord(media_type=WatchEntryMediaType.MOVIE, tmdb_id=tmdb_id, watched_at=watched_at, origin=file_name))
                            continue
                    elif item_type == WatchEntryMediaType.EPISODE:
                        show = record.get('show') or {}
                        episode = record.get('episode') or {}
                        tmdb_id = _safe_int(show.get('ids', {}).get('tmdb'))
                        season_number = _safe_int(episode.get('season'))
                        episode_number = _safe_int(episode.get('number'))
                        if tmdb_id and season_number is not None and episode_number is not None:
                            records.append(
                                WatchEntryRecord(
                                    media_type=WatchEntryMediaType.EPISODE,
                                    tmdb_id=tmdb_id,
                                    watched_at=watched_at,
                                    season_number=season_number,
                                    episode_number=episode_number,
                                    origin=file_name,
                                )
                            )
                            continue
                    invalid_count += 1

                elif lower.startswith('watched-movies-'):
                    tmdb_id = _safe_int((record.get('movie') or {}).get('ids', {}).get('tmdb'))
                    if not tmdb_id:
                        invalid_count += 1
                        continue
                    records.append(
                        WatchEntryRecord(
                            media_type=WatchEntryMediaType.MOVIE,
                            tmdb_id=tmdb_id,
                            watched_at=_parse_watched_at(record.get('last_watched_at') or record.get('last_updated_at')),
                            origin=file_name,
                        )
                    )

                elif lower == 'lists-watchlist.json':
                    media_type, tmdb_id = _media_from_record(record)
                    if not tmdb_id:
                        invalid_count += 1
                        continue
                    records.append(StatusRecord(media_type=media_type, tmdb_id=tmdb_id, status=TvShowStatus.PLAN_TO_WATCH, origin=file_name))

                elif lower.startswith('ratings-movies-') or lower == 'ratings-shows.json':
                    media_type, tmdb_id = _media_from_record(record)
                    score = _safe_int(record.get('rating'))
                    if not tmdb_id or not score:
                        invalid_count += 1
                        continue
                    records.append(RatingRecord(media_type=media_type, tmdb_id=tmdb_id, score=score, origin=file_name))

                elif lower in ('hidden-progress-watched.json', 'hidden-progress-watched-reset.json'):
                    media_type, tmdb_id = _media_from_record(record)
                    if not tmdb_id:
                        invalid_count += 1
                        continue
                    records.append(StatusRecord(media_type=MediaType.TV, tmdb_id=tmdb_id, status=TvShowStatus.DROPPED, origin=file_name))

                elif lower == 'watched-shows.json':
                    # Show-level history entries carry no per-episode data here;
                    # they only guarantee show metadata exists.
                    tmdb_id = _safe_int((record.get('show') or {}).get('ids', {}).get('tmdb'))
                    if not tmdb_id:
                        invalid_count += 1
                        continue
                    metadata_only_count += 1
                    show_ids.add(tmdb_id)

                else:
                    unsupported_records += 1
                    invalid_count += 1

            files_report.append(file_report)

    summary = {
        'watch_history': sum(1 for r in records if isinstance(r, WatchEntryRecord)),
        'watchlist': sum(1 for r in records if isinstance(r, StatusRecord) and r.status == TvShowStatus.PLAN_TO_WATCH),
        'ratings': sum(1 for r in records if isinstance(r, RatingRecord)),
    }
    report = {
        'format': DataTransferFormat.ZIP,
        'files_processed': files_processed,
        'files_failed': files_failed,
        'unsupported_files': unsupported_files,
        'unsupported_records': unsupported_records,
        'metadata_only_shows': metadata_only_count,
        'records_seen': sum(f['records_seen'] for f in files_report),
        'invalid_count': invalid_count,
        'summary': summary,
        'total_items': sum(f['records_seen'] for f in files_report),
        'files': files_report,
    }
    return ParsedImport(
        records=tuple(records),
        collections_present=frozenset(collections),
        invalid_count=invalid_count,
        report=report,
        prefetch_only_ids={MediaType.TV: frozenset(show_ids)},
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

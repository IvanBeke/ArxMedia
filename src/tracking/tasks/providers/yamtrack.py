"""Yamtrack CSV import provider: pure parsing only (no DB/TMDB access)."""

import csv
import io
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

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
    add_import_warning,
)

YAMTRACK_ALLOWED_MEDIA_TYPES = {'movie', 'tv', 'episode'}
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


# Watched dates come exclusively from end_date; every other timestamp column
# is yamtrack-internal. Rows without one import with the epoch as "unknown".


def _yamtrack_watch_entry_status(value: str) -> str | None:
    return {('Completed'): TvShowStatus.WATCHED}.get(value)


def _yamtrack_movie_collections(status: str, score: int | None, collections: set[str]) -> None:
    if status in {'Completed', 'In progress', 'Paused', 'Dropped'}:
        collections.add(WATCH_HISTORY_COLLECTION)
    if status == 'Planning':
        collections.add(WATCHLIST_COLLECTION)
    if score:
        collections.add(RATINGS_COLLECTION)


def _yamtrack_tv_collections(status: str, score: int | None, collections: set[str]) -> None:
    if status == 'Planning':
        collections.add(WATCHLIST_COLLECTION)
    if score:
        collections.add(RATINGS_COLLECTION)


def _yamtrack_episode_collections(status: str, end_at, progressed_at, collections: set[str]) -> None:
    # Episode watches are recorded via progress events; a progressed
    # timestamp (even without end_date/status) marks the episode watched.
    if status in {'Completed', 'In progress', 'Paused', 'Dropped'} or not status and (end_at or progressed_at):
        collections.add(WATCH_HISTORY_COLLECTION)


def _yamtrack_collection_from_row(media_type: str, status: str, score: int | None, end_at, progressed_at) -> set[str]:
    collections: set[str] = set()
    if media_type == 'movie':
        _yamtrack_movie_collections(status, score, collections)
    elif media_type == 'episode':
        _yamtrack_episode_collections(status, end_at, progressed_at, collections)
    elif media_type == 'tv':
        _yamtrack_tv_collections(status, score, collections)
    return collections


def _yamtrack_row_timestamp(row: dict, *fields: str) -> datetime | None:
    """First non-empty timestamp among fields, imported verbatim."""
    for field in fields:
        parsed = _parse_watched_at(row.get(field))
        if parsed:
            return parsed
    return None


class _YamtrackState:
    """Mutable state threaded through the per-row handling."""

    def __init__(self) -> None:
        self.records: list[WatchEntryRecord | StatusRecord | RatingRecord] = []
        self.invalid_count = 0
        self.skip_breakdown: dict[str, int] = {
            'skipped_non_tmdb': 0,
            'skipped_unsupported_media_type': 0,
            'skipped_invalid_status': 0,
            'skipped_missing_tmdb_id': 0,
        }
        self.collections: set[str] = set()
        self.warnings: list[dict] = []
        self.row_count = 0


def _yamtrack_reject(state: _YamtrackState, code: str, message: str, column: str, counter: str) -> None:
    state.invalid_count += 1
    state.skip_breakdown[counter] += 1
    add_import_warning(
        state.warnings, code, message,
        {'kind': 'csv_row', 'file': 'yamtrack.csv', 'row': state.row_count + 1, 'column': column},
    )


def _validate_yamtrack_row(state: _YamtrackState, source: str, media_type: str, status: str, tmdb_id: int | None) -> bool:
    if source != 'tmdb':
        _yamtrack_reject(state, 'non_tmdb_source', 'Only rows with source tmdb can be imported.', 'source', 'skipped_non_tmdb')
        return False
    if media_type not in YAMTRACK_ALLOWED_MEDIA_TYPES:
        _yamtrack_reject(state, 'unsupported_media_type', 'The row uses an unsupported media type.', 'media_type', 'skipped_unsupported_media_type')
        return False
    if status not in YAMTRACK_ALLOWED_STATUSES:
        _yamtrack_reject(state, 'invalid_status', 'The row uses a status that cannot be imported.', 'status', 'skipped_invalid_status')
        return False
    if not tmdb_id:
        _yamtrack_reject(state, 'missing_tmdb_id', 'The row does not contain a TMDB ID.', 'media_id', 'skipped_missing_tmdb_id')
        return False
    return True


def _yamtrack_row_fields(row: dict) -> dict[str, Any]:
    """Normalized field values for one yamtrack CSV row."""
    return {
        'source': (row.get('source') or '').strip().lower(),
        'media_type': (row.get('media_type') or '').strip().lower(),
        'status': (row.get('status') or '').strip(),
        'tmdb_id': _safe_int(row.get('media_id')),
        'season_number': _safe_int(row.get('season_number')),
        'episode_number': _safe_int(row.get('episode_number')),
        'score': _parse_yamtrack_score(row.get('score')),
        'progressed_at': _parse_watched_at(row.get('progressed_at')),
        'end_at': _parse_watched_at(row.get('end_date')),
        'created_at': _parse_watched_at(row.get('created_at')),
    }


def _handle_yamtrack_movie(state: _YamtrackState, fields: dict[str, Any]) -> None:
    status = fields['status']
    entry_status = _yamtrack_watch_entry_status(status)
    if entry_status:
        state.records.append(
            WatchEntryRecord(
                media_type=WatchEntryMediaType.MOVIE,
                tmdb_id=fields['tmdb_id'],
                watched_at=fields['event_at'],
            )
        )
    if status == 'Planning':
        state.records.append(
            StatusRecord(media_type=MediaType.MOVIE, tmdb_id=fields['tmdb_id'], status=TvShowStatus.PLAN_TO_WATCH, status_at=fields['event_at'])
        )
    if status == 'Dropped':
        state.records.append(
            StatusRecord(media_type=MediaType.MOVIE, tmdb_id=fields['tmdb_id'], status=TvShowStatus.DROPPED, status_at=fields['event_at'])
        )
    if fields['score']:
        state.records.append(RatingRecord(media_type=MediaType.MOVIE, tmdb_id=fields['tmdb_id'], score=fields['score']))


def _handle_yamtrack_tv(state: _YamtrackState, fields: dict[str, Any]) -> None:
    # Watching/watched are derived from episode history by the
    # reconciliation pass; only plan/dropped are preserved as-is.
    if fields['status'] == 'Dropped':
        state.records.append(
            StatusRecord(media_type=MediaType.TV, tmdb_id=fields['tmdb_id'], status=TvShowStatus.DROPPED, status_at=fields['event_at'])
        )
    if fields['status'] == 'Planning':
        state.records.append(
            StatusRecord(media_type=MediaType.TV, tmdb_id=fields['tmdb_id'], status=TvShowStatus.PLAN_TO_WATCH, status_at=fields['event_at'])
        )
    if fields['score']:
        state.records.append(RatingRecord(media_type=MediaType.TV, tmdb_id=fields['tmdb_id'], score=fields['score']))


def _yamtrack_episode_entry_status(status: str, end_at, progressed_at) -> str | None:
    entry_status = _yamtrack_watch_entry_status(status)
    if not entry_status and (end_at or progressed_at):
        # Progress events mark episodes watched even without status/end_date.
        return TvShowStatus.WATCHED
    return entry_status


def _yamtrack_missing_number_column(season_number, episode_number) -> str:
    return 'season_number' if season_number is None else 'episode_number'


def _flag_missing_yamtrack_number(
    state: _YamtrackState, season_number, episode_number, end_at, progressed_at, entry_status,
) -> None:
    if not (end_at or progressed_at or entry_status):
        return
    state.invalid_count += 1
    add_import_warning(
        state.warnings, 'missing_episode_number', 'The episode row is missing a season or episode number.',
        {'kind': 'csv_row', 'file': 'yamtrack.csv', 'row': state.row_count + 1,
         'column': _yamtrack_missing_number_column(season_number, episode_number)},
    )


def _handle_yamtrack_episode(state: _YamtrackState, fields: dict[str, Any]) -> None:
    entry_status = _yamtrack_episode_entry_status(fields['status'], fields['end_at'], fields['progressed_at'])
    if entry_status and fields['season_number'] is not None and fields['episode_number'] is not None:
        state.records.append(
            WatchEntryRecord(
                media_type=WatchEntryMediaType.EPISODE,
                tmdb_id=fields['tmdb_id'],
                watched_at=fields['event_at'],
                season_number=fields['season_number'],
                episode_number=fields['episode_number'],
            )
        )
        return
    _flag_missing_yamtrack_number(
        state, fields['season_number'], fields['episode_number'], fields['end_at'], fields['progressed_at'], entry_status,
    )


def _dispatch_yamtrack_row(state: _YamtrackState, fields: dict[str, Any]) -> None:
    media_type = fields['media_type']
    if media_type == 'movie':
        _handle_yamtrack_movie(state, fields)
        return
    if media_type == 'tv':
        _handle_yamtrack_tv(state, fields)
        return
    _handle_yamtrack_episode(state, fields)


def _handle_yamtrack_row(state: _YamtrackState, row: dict) -> None:
    state.row_count += 1
    fields = _yamtrack_row_fields(row)
    fields['event_at'] = fields['end_at'] or fields['progressed_at'] or fields['created_at']

    state.collections.update(_yamtrack_collection_from_row(
        fields['media_type'], fields['status'], fields['score'], fields['end_at'], fields['progressed_at'],
    ))
    if not _validate_yamtrack_row(state, fields['source'], fields['media_type'], fields['status'], fields['tmdb_id']):
        return
    _dispatch_yamtrack_row(state, fields)


def _yamtrack_summary(records: list) -> dict:
    summary = {'watch_history': 0, 'watchlist': 0, 'ratings': 0}
    for record in records:
        if isinstance(record, WatchEntryRecord):
            summary['watch_history'] += 1
        elif isinstance(record, StatusRecord) and record.status == TvShowStatus.PLAN_TO_WATCH:
            summary['watchlist'] += 1
        elif isinstance(record, RatingRecord):
            summary['ratings'] += 1
    return summary


def _yamtrack_report(state: _YamtrackState) -> dict:
    return {
        'format': DataTransferFormat.CSV,
        'records_seen': state.row_count,
        'invalid_count': state.invalid_count,
        'summary': _yamtrack_summary(state.records),
        'total_items': state.row_count,
        **state.skip_breakdown,
        'warnings': state.warnings,
        'warnings_total': state.invalid_count,
        'warnings_truncated': state.invalid_count > len(state.warnings),
    }


def parse_yamtrack_csv(content: bytes) -> ParsedImport:
    state = _YamtrackState()
    reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig')))

    for row in reader:
        _handle_yamtrack_row(state, row)

    return ParsedImport(
        records=tuple(state.records),
        collections_present=frozenset(state.collections),
        invalid_count=state.invalid_count,
        report=_yamtrack_report(state),
    )


def analyze_yamtrack_csv(content: bytes) -> dict:
    parsed = parse_yamtrack_csv(content)
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

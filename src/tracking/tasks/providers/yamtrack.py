"""Yamtrack CSV import provider: pure parsing only (no DB/TMDB access)."""

import csv
import io
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

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
UNKNOWN_WATCHED_DATE = datetime(1970, 1, 1, tzinfo=UTC)


def _yamtrack_watch_entry_status(value: str) -> str | None:
    return {('Completed'): TvShowStatus.WATCHED}.get(value)


def _yamtrack_collection_from_row(media_type: str, status: str, score: int | None, end_at, progressed_at) -> set[str]:
    collections: set[str] = set()
    if media_type == 'movie':
        if status in {'Completed', 'In progress', 'Paused', 'Dropped'}:
            collections.add(WATCH_HISTORY_COLLECTION)
        if status == 'Planning':
            collections.add(WATCHLIST_COLLECTION)
    elif media_type == 'episode':
        # Episode watches are recorded via progress events; a progressed
        # timestamp (even without end_date/status) marks the episode watched.
        if status in {'Completed', 'In progress', 'Paused', 'Dropped'} or not status and (end_at or progressed_at):
            collections.add(WATCH_HISTORY_COLLECTION)
    elif media_type == 'tv':
        if status == 'Planning':
            collections.add(WATCHLIST_COLLECTION)

    if media_type in {'movie', 'tv'} and score:
        collections.add(RATINGS_COLLECTION)
    return collections


def parse_yamtrack_csv(content: bytes) -> ParsedImport:
    records: list[WatchEntryRecord | StatusRecord | RatingRecord] = []
    invalid_count = 0
    skip_breakdown = {
        'skipped_non_tmdb': 0,
        'skipped_unsupported_media_type': 0,
        'skipped_invalid_status': 0,
        'skipped_missing_tmdb_id': 0,
    }
    collections: set[str] = set()

    reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig')))
    row_count = 0
    for row in reader:
        row_count += 1
        source = (row.get('source') or '').strip().lower()
        media_type = (row.get('media_type') or '').strip().lower()
        status = (row.get('status') or '').strip()
        tmdb_id = _safe_int(row.get('media_id'))
        season_number = _safe_int(row.get('season_number'))
        episode_number = _safe_int(row.get('episode_number'))
        score = _parse_yamtrack_score(row.get('score'))
        progressed_at = _parse_watched_at(row.get('progressed_at'))
        end_at = _parse_watched_at(row.get('end_date'))
        event_at = end_at if end_at is not None else UNKNOWN_WATCHED_DATE

        collections.update(_yamtrack_collection_from_row(media_type, status, score, end_at, progressed_at))

        if source != 'tmdb':
            invalid_count += 1
            skip_breakdown['skipped_non_tmdb'] += 1
            continue
        if media_type not in YAMTRACK_ALLOWED_MEDIA_TYPES:
            invalid_count += 1
            skip_breakdown['skipped_unsupported_media_type'] += 1
            continue
        if status not in YAMTRACK_ALLOWED_STATUSES:
            invalid_count += 1
            skip_breakdown['skipped_invalid_status'] += 1
            continue
        if not tmdb_id:
            invalid_count += 1
            skip_breakdown['skipped_missing_tmdb_id'] += 1
            continue

        if media_type == 'movie':
            entry_status = _yamtrack_watch_entry_status(status)
            if entry_status:
                records.append(
                    WatchEntryRecord(
                        media_type=WatchEntryMediaType.MOVIE,
                        tmdb_id=tmdb_id,
                        watched_at=event_at,
                    )
                )
            if status == 'Planning':
                records.append(
                    StatusRecord(media_type=MediaType.MOVIE, tmdb_id=tmdb_id, status=TvShowStatus.PLAN_TO_WATCH, status_at=event_at)
                )
            if status == 'Dropped':
                records.append(
                    StatusRecord(media_type=MediaType.MOVIE, tmdb_id=tmdb_id, status=TvShowStatus.DROPPED, status_at=event_at)
                )
            if score:
                records.append(RatingRecord(media_type=MediaType.MOVIE, tmdb_id=tmdb_id, score=score))

        elif media_type == 'tv':
            # Watching/watched are derived from episode history by the
            # reconciliation pass; only plan/dropped are preserved as-is.
            if status == 'Dropped':
                records.append(
                    StatusRecord(media_type=MediaType.TV, tmdb_id=tmdb_id, status=TvShowStatus.DROPPED, status_at=event_at)
                )
            if status == 'Planning':
                records.append(
                    StatusRecord(media_type=MediaType.TV, tmdb_id=tmdb_id, status=TvShowStatus.PLAN_TO_WATCH, status_at=event_at)
                )
            if score:
                records.append(RatingRecord(media_type=MediaType.TV, tmdb_id=tmdb_id, score=score))

        elif media_type == 'episode':
            entry_status = _yamtrack_watch_entry_status(status)
            progressed_at = _parse_watched_at(row.get('progressed_at'))
            if not entry_status and (end_at or progressed_at):
                # Progress events mark episodes watched even without status/end_date.
                entry_status = TvShowStatus.WATCHED
            if entry_status and season_number is not None and episode_number is not None:
                records.append(
                    WatchEntryRecord(
                        media_type=WatchEntryMediaType.EPISODE,
                        tmdb_id=tmdb_id,
                        watched_at=event_at,
                        season_number=season_number,
                        episode_number=episode_number,
                    )
                )

    summary = {
        'watch_history': sum(1 for r in records if isinstance(r, WatchEntryRecord)),
        'watchlist': sum(1 for r in records if isinstance(r, StatusRecord) and r.status == TvShowStatus.PLAN_TO_WATCH),
        'ratings': sum(1 for r in records if isinstance(r, RatingRecord)),
    }
    report = {
        'format': DataTransferFormat.CSV,
        'records_seen': row_count,
        'invalid_count': invalid_count,
        'summary': summary,
        'total_items': row_count,
        **skip_breakdown,
    }
    return ParsedImport(
        records=tuple(records),
        collections_present=frozenset(collections),
        invalid_count=invalid_count,
        report=report,
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

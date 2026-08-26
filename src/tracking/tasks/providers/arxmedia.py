"""ArxMedia JSON import provider: pure parsing only (no DB/TMDB access)."""

import json

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


def _report(records: tuple, collections: frozenset[str], invalid_count: int, unit_count: int) -> dict:
    summary = {
        'watch_history': sum(1 for r in records if isinstance(r, WatchEntryRecord)),
        'watchlist': sum(1 for r in records if isinstance(r, StatusRecord) and r.status == TvShowStatus.PLAN_TO_WATCH),
        'ratings': sum(1 for r in records if isinstance(r, RatingRecord)),
    }
    return {
        'format': DataTransferFormat.JSON,
        'records_seen': unit_count,
        'invalid_count': invalid_count,
        'summary': summary,
        'total_items': unit_count,
    }


def parse_arxmedia_json(content: bytes) -> ParsedImport:
    data = json.loads(content.decode('utf-8') or '{}')
    history = data.get('watch_history', [])
    watchlist = data.get('watchlist', [])
    ratings = data.get('ratings', [])

    records: list[WatchEntryRecord | StatusRecord | RatingRecord] = []
    invalid_count = 0

    for item in history:
        media_type = item.get('media_type', WatchEntryMediaType.MOVIE)
        tmdb_id = _safe_int(item.get('tmdb_id'))
        if not tmdb_id:
            invalid_count += 1
            continue
        records.append(
            WatchEntryRecord(
                media_type=media_type,
                tmdb_id=tmdb_id,
                watched_at=_parse_watched_at(item.get('watched_at')),
                season_number=_safe_int(item.get('season_number')),
                episode_number=_safe_int(item.get('episode_number')),
            )
        )

    for item in watchlist:
        media_type = item.get('media_type', MediaType.MOVIE)
        tmdb_id = _safe_int(item.get('tmdb_id'))
        if not tmdb_id:
            invalid_count += 1
            continue
        records.append(StatusRecord(media_type=media_type, tmdb_id=tmdb_id, status=TvShowStatus.PLAN_TO_WATCH))

    for item in ratings:
        score = _safe_int(item.get('score'))
        media_type = item.get('media_type', MediaType.MOVIE)
        tmdb_id = _safe_int(item.get('tmdb_id'))
        if not score or not tmdb_id:
            invalid_count += 1
            continue
        records.append(RatingRecord(media_type=media_type, tmdb_id=tmdb_id, score=score))

    collections: set[str] = set()
    if history:
        collections.add(WATCH_HISTORY_COLLECTION)
    if watchlist:
        collections.add(WATCHLIST_COLLECTION)
    if ratings:
        collections.add(RATINGS_COLLECTION)

    unit_count = len(history) + len(watchlist) + len(ratings)
    parsed = ParsedImport(
        records=tuple(records),
        collections_present=frozenset(collections),
        invalid_count=invalid_count,
        report=_report(tuple(records), frozenset(collections), invalid_count, unit_count),
    )
    return parsed


def analyze_arxmedia_json(content: bytes) -> dict:
    parsed = parse_arxmedia_json(content)
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

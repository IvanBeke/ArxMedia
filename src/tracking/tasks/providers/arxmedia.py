import json
from typing import Any

from ...choices import DataTransferFormat, MediaType, TvShowStatus
from ...models import DataTransferJob
from ..shared import (
    _ensure_tmdb_metadata_for_import_item,
    _import_rating_by_mode,
    _import_tv_status_by_mode,
    _import_watch_entry_by_mode,
    _parse_watched_at,
    _safe_int,
    _update_job_progress,
)


def analyze_arxmedia_json(content: bytes) -> dict:
    data = json.loads(content.decode('utf-8') or '{}')
    history = data.get('watch_history', [])
    watchlist = data.get('watchlist', [])
    ratings = data.get('ratings', [])

    return {
        'format': DataTransferFormat.JSON,
        'records_seen': len(history) + len(watchlist) + len(ratings),
        'records_imported': 0,
        'records_skipped': 0,
        'metadata_hits': 0,
        'metadata_fetches': 0,
        'metadata_errors': 0,
        'summary': {
            'watch_history': len(history),
            'watchlist': len(watchlist),
            'ratings': len(ratings),
        },
        'total_items': len(history) + len(watchlist) + len(ratings),
    }


def apply_arxmedia_json_import(job: DataTransferJob, content: bytes, import_mode: str):
    data = json.loads(content.decode('utf-8') or '{}')
    history = data.get('watch_history', [])
    watchlist = data.get('watchlist', [])
    ratings = data.get('ratings', [])

    metadata_state: dict[str, Any] = {
        'metadata_checked': set(),
        'season_checked': set(),
        'metadata_hits': 0,
        'metadata_fetches': 0,
        'metadata_errors': 0,
    }
    report: dict[str, Any] = {
        'format': DataTransferFormat.JSON,
        'records_seen': len(history) + len(watchlist) + len(ratings),
        'records_imported': 0,
        'records_skipped': 0,
        'metadata_hits': 0,
        'metadata_fetches': 0,
        'metadata_errors': 0,
        'summary': {
            'watch_history': 0,
            'watchlist': 0,
            'ratings': 0,
        },
        'total_items': job.total_items,
    }

    for item in history:
        media_type = item.get('media_type', MediaType.MOVIE)
        tmdb_id = _safe_int(item.get('tmdb_id'))
        season_number = _safe_int(item.get('season_number'))
        episode_number = _safe_int(item.get('episode_number'))
        if not tmdb_id:
            report['records_skipped'] += 1
            job.processed_items += 1
            _update_job_progress(job)
            continue

        _ensure_tmdb_metadata_for_import_item(media_type, tmdb_id, metadata_state, season_number=season_number)
        changed = _import_watch_entry_by_mode(
            job.user,
            media_type,
            tmdb_id,
            _parse_watched_at(item.get('watched_at')),
            import_mode,
            season_number=season_number,
            episode_number=episode_number,
        )
        if changed:
            report['records_imported'] += 1
            report['summary']['watch_history'] += 1
        else:
            report['records_skipped'] += 1

        job.processed_items += 1
        _update_job_progress(job)

    for item in watchlist:
        media_type = item.get('media_type', MediaType.MOVIE)
        tmdb_id = _safe_int(item.get('tmdb_id'))
        if not tmdb_id:
            report['records_skipped'] += 1
            job.processed_items += 1
            _update_job_progress(job)
            continue

        _ensure_tmdb_metadata_for_import_item(media_type, tmdb_id, metadata_state)
        changed = _import_tv_status_by_mode(
            job.user,
            media_type,
            tmdb_id,
            TvShowStatus.PLAN_TO_WATCH,
            None,
            None,
            import_mode,
        )
        if changed:
            report['records_imported'] += 1
            report['summary']['watchlist'] += 1
        else:
            report['records_skipped'] += 1

        job.processed_items += 1
        _update_job_progress(job)

    for item in ratings:
        score = _safe_int(item.get('score'))
        media_type = item.get('media_type', MediaType.MOVIE)
        tmdb_id = _safe_int(item.get('tmdb_id'))
        if not score or not tmdb_id:
            report['records_skipped'] += 1
            job.processed_items += 1
            _update_job_progress(job)
            continue

        _ensure_tmdb_metadata_for_import_item(media_type, tmdb_id, metadata_state)
        changed = _import_rating_by_mode(job.user, media_type, tmdb_id, score, import_mode)
        if changed:
            report['records_imported'] += 1
            report['summary']['ratings'] += 1
        else:
            report['records_skipped'] += 1

        job.processed_items += 1
        _update_job_progress(job)

    report['metadata_hits'] = metadata_state['metadata_hits']
    report['metadata_fetches'] = metadata_state['metadata_fetches']
    report['metadata_errors'] = metadata_state['metadata_errors']
    report['total_items'] = job.total_items
    job.metadata = report
    job.save(update_fields=['total_items', 'processed_items', 'metadata', 'updated_at'])

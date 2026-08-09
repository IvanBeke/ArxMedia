from celery import shared_task
from django.core.files.base import ContentFile

import csv
import io
import json

from ..choices import DataImportMode, DataTransferFormat, DataTransferStatus, MediaType, WatchEntryStatus
from ..models import DataTransferJob, Rating, Review, WatchEntry, Watchlist
from .shared import (
    _analyze_trakt_zip,
    _apply_trakt_zip,
    _ensure_tmdb_metadata_for_import_item,
    _parse_watched_at,
    _safe_int,
    _update_job_progress,
    _upsert_watch_entry,
)


@shared_task(name="tracking.export_user_data")
def export_user_data(job_id: int) -> dict[str, str]:
    job = DataTransferJob.objects.get(id=job_id)
    job.status = DataTransferStatus.PROCESSING
    job.save(update_fields=['status', 'updated_at'])

    try:
        user = job.user
        payload = {
            'watch_history': list(WatchEntry.objects.filter(user=user).values()),
            'watchlist': list(Watchlist.objects.filter(user=user).values()),
            'ratings': list(Rating.objects.filter(user=user).values()),
            'reviews': list(Review.objects.filter(user=user).values()),
        }
        if job.data_format == DataTransferFormat.CSV:
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(['collection', 'media_type', 'tmdb_id', 'status', 'season_number', 'episode_number', 'score', 'content'])
            for item in payload['watch_history']:
                writer.writerow(['watch_history', item.get('media_type'), item.get('tmdb_id'), item.get('status'), item.get('season_number'), item.get('episode_number'), '', ''])
            for item in payload['watchlist']:
                writer.writerow(['watchlist', item.get('media_type'), item.get('tmdb_id'), '', '', '', '', ''])
            for item in payload['ratings']:
                writer.writerow(['ratings', item.get('media_type'), item.get('tmdb_id'), '', '', '', item.get('score'), ''])
            for item in payload['reviews']:
                writer.writerow(['reviews', item.get('media_type'), item.get('tmdb_id'), '', '', '', '', item.get('content', '')])
            raw = buffer.getvalue()
            filename = f'user-{user.id}-export-{job.id}.csv'
        else:
            raw = json.dumps(payload, default=str, indent=2)
            filename = f'user-{user.id}-export-{job.id}.json'
        job.output_file.save(filename, ContentFile(raw.encode('utf-8')), save=False)
        job.status = DataTransferStatus.DONE
        job.total_items = sum(len(v) for v in payload.values())
        job.processed_items = job.total_items
        job.error_message = ''
        job.save()
        return {'status': DataTransferStatus.DONE}
    except Exception as exc:
        job.status = DataTransferStatus.FAILED
        job.error_message = str(exc)
        job.save(update_fields=['status', 'error_message', 'updated_at'])
        return {'status': DataTransferStatus.FAILED}


@shared_task(name="tracking.import_user_data")
def import_user_data(job_id: int) -> dict[str, str]:
    job = DataTransferJob.objects.get(id=job_id)
    job.status = DataTransferStatus.PROCESSING
    job.save(update_fields=['status', 'updated_at'])

    try:
        content = job.input_file.read() if job.input_file else b''
        job.total_items = 0
        job.processed_items = 0
        job.metadata = {}
        job.save(update_fields=['total_items', 'processed_items', 'metadata', 'updated_at'])

        metadata_state = {
            'metadata_checked': set(),
            'season_checked': set(),
            'metadata_hits': 0,
            'metadata_fetches': 0,
            'metadata_errors': 0,
        }

        history = []
        watchlist = []
        ratings = []
        if job.data_format == DataTransferFormat.CSV:
            reader = csv.DictReader(io.StringIO(content.decode('utf-8')))
            for row in reader:
                if row.get('collection') != 'watch_history':
                    continue
                history.append({
                    'media_type': row.get('media_type') or MediaType.MOVIE,
                    'tmdb_id': int(row.get('tmdb_id') or 0),
                    'status': row.get('status') or WatchEntryStatus.WATCHED,
                    'season_number': int(row['season_number']) if row.get('season_number') else None,
                    'episode_number': int(row['episode_number']) if row.get('episode_number') else None,
                    'watched_at': _parse_watched_at(row.get('watched_at')),
                })
        elif job.data_format == DataTransferFormat.ZIP:
            report = _analyze_trakt_zip(job, content)
            job.total_items = report.get('total_items', 0)
            job.processed_items = 0
            job.metadata = report
            job.save(update_fields=['total_items', 'processed_items', 'metadata', 'updated_at'])
            _apply_trakt_zip(job, content, DataImportMode.NEW_ITEMS)
            metadata = dict(job.metadata or {})
            metadata['import_mode'] = DataImportMode.NEW_ITEMS
            job.metadata = metadata
            job.status = DataTransferStatus.DONE
            job.error_message = ''
            job.save(update_fields=['status', 'error_message', 'metadata', 'updated_at'])
            return {'status': DataTransferStatus.DONE}
        else:
            data = json.loads(content.decode('utf-8') or '{}')
            history = data.get('watch_history', [])
            watchlist = data.get('watchlist', [])
            ratings = data.get('ratings', [])

        job.total_items = len(history) + len(watchlist) + len(ratings)
        job.processed_items = 0
        job.metadata = {'format': job.data_format}
        job.save(update_fields=['total_items', 'processed_items', 'metadata', 'updated_at'])

        for item in history:
            media_type = item.get('media_type', MediaType.MOVIE)
            tmdb_id = _safe_int(item.get('tmdb_id'))
            season_number = _safe_int(item.get('season_number'))
            episode_number = _safe_int(item.get('episode_number'))
            if not tmdb_id:
                job.processed_items += 1
                _update_job_progress(job)
                continue

            _ensure_tmdb_metadata_for_import_item(media_type, tmdb_id, metadata_state, season_number=season_number)
            _upsert_watch_entry(
                job.user,
                media_type,
                tmdb_id,
                _parse_watched_at(item.get('watched_at')),
                season_number=season_number,
                episode_number=episode_number,
            )
            job.processed_items += 1
            _update_job_progress(job)

        for item in watchlist:
            media_type = item.get('media_type', MediaType.MOVIE)
            tmdb_id = _safe_int(item.get('tmdb_id'))
            if not tmdb_id:
                job.processed_items += 1
                _update_job_progress(job)
                continue

            _ensure_tmdb_metadata_for_import_item(media_type, tmdb_id, metadata_state)
            Watchlist.objects.update_or_create(
                user=job.user,
                media_type=media_type,
                tmdb_id=tmdb_id,
                defaults={
                    'notes': item.get('notes', ''),
                },
            )
            job.processed_items += 1
            _update_job_progress(job)

        for item in ratings:
            score = _safe_int(item.get('score'))
            media_type = item.get('media_type', MediaType.MOVIE)
            tmdb_id = _safe_int(item.get('tmdb_id'))
            if not score or not tmdb_id:
                job.processed_items += 1
                _update_job_progress(job)
                continue
            _ensure_tmdb_metadata_for_import_item(media_type, tmdb_id, metadata_state)
            Rating.objects.update_or_create(
                user=job.user,
                media_type=media_type,
                tmdb_id=tmdb_id,
                defaults={
                    'score': score,
                },
            )
            job.processed_items += 1
            _update_job_progress(job)

        job.metadata = {
            'format': job.data_format,
            'metadata_hits': metadata_state['metadata_hits'],
            'metadata_fetches': metadata_state['metadata_fetches'],
            'metadata_errors': metadata_state['metadata_errors'],
        }

        job.status = DataTransferStatus.DONE
        job.error_message = ''
        job.save(update_fields=['status', 'processed_items', 'error_message', 'metadata', 'updated_at'])
        return {'status': DataTransferStatus.DONE}
    except Exception as exc:
        job.status = DataTransferStatus.FAILED
        job.error_message = str(exc)
        job.save(update_fields=['status', 'error_message', 'updated_at'])
        return {'status': DataTransferStatus.FAILED}

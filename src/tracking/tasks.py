from celery import shared_task
from django.utils import timezone
from django.core.files.base import ContentFile
import csv
import io
import json
import logging
import re
import zipfile
from datetime import datetime
from media.tmdb import tmdb
from media.models import Movie, TVShow, Season

from .choices import (
    DataImportMode,
    DataTransferFormat,
    DataTransferStatus,
    MediaType,
    WatchEntryMediaType,
    WatchEntryStatus,
)
from .models import DataTransferJob, WatchEntry, Watchlist, Rating, Review


logger = logging.getLogger(__name__)


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
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except Exception:
        return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


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
        lower.startswith('watched-history-')
        or lower.startswith('watched-movies-')
        or lower == 'watched-shows.json'
        or lower == 'lists-watchlist.json'
        or lower.startswith('ratings-movies-')
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
    if lower.startswith('watched-history-') or lower.startswith('watched-movies-'):
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
    report = _default_import_report()
    report['summary'] = {
        'watch_history': 0,
        'watchlist': 0,
        'ratings': 0,
    }

    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        file_names = sorted((name for name in archive.namelist() if name.lower().endswith('.json')), key=_zip_json_sort_key)

        for name in file_names:
            file_name = name.rsplit('/', 1)[-1]
            file_report = {
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
        for item in Rating.objects.filter(user=job.user):
            key = _rating_key(item.media_type, item.tmdb_id)
            if key not in imported_keys['ratings']:
                delete_ids.append(item.id)
        if delete_ids:
            Rating.objects.filter(id__in=delete_ids).delete()


def _apply_trakt_zip(job: DataTransferJob, content: bytes, import_mode: str):
    report = _default_import_report()
    state = {
        'metadata_checked': set(),
        'season_checked': set(),
        'metadata_hits': 0,
        'metadata_fetches': 0,
        'metadata_errors': 0,
    }
    imported_keys = {
        'watch_entries': set(),
        'watchlist': set(),
        'ratings': set(),
    }
    collections_present = set()

    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        file_names = sorted((name for name in archive.namelist() if name.lower().endswith('.json')), key=_zip_json_sort_key)

        for name in file_names:
            file_name = name.rsplit('/', 1)[-1]
            file_report = {
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


@shared_task(name="tracking.prepare_trakt_zip_import")
def prepare_trakt_zip_import(job_id: int) -> dict[str, str]:
    job = DataTransferJob.objects.get(id=job_id)
    job.status = DataTransferStatus.PROCESSING
    job.save(update_fields=['status', 'updated_at'])

    try:
        content = job.input_file.read() if job.input_file else b''
        report = _analyze_trakt_zip(job, content)
        job.total_items = report.get('total_items', 0)
        job.processed_items = 0
        job.metadata = report
        job.status = DataTransferStatus.AWAITING_CONFIRMATION
        job.error_message = ''
        job.save(update_fields=['total_items', 'processed_items', 'metadata', 'status', 'error_message', 'updated_at'])
        return {'status': DataTransferStatus.AWAITING_CONFIRMATION}
    except Exception as exc:
        job.status = DataTransferStatus.FAILED
        job.error_message = str(exc)
        job.save(update_fields=['status', 'error_message', 'updated_at'])
        return {'status': DataTransferStatus.FAILED}


@shared_task(name="tracking.apply_trakt_zip_import")
def apply_trakt_zip_import(job_id: int) -> dict[str, str]:
    job = DataTransferJob.objects.get(id=job_id)
    try:
        import_mode = (job.metadata or {}).get('import_mode') or DataImportMode.NEW_ITEMS
        if import_mode not in DataImportMode.values:
            import_mode = DataImportMode.NEW_ITEMS
        content = job.input_file.read() if job.input_file else b''
        job.processed_items = 0
        job.total_items = (job.metadata or {}).get('total_items', job.total_items)
        job.save(update_fields=['processed_items', 'total_items', 'updated_at'])

        _apply_trakt_zip(job, content, import_mode)
        metadata = dict(job.metadata or {})
        metadata['import_mode'] = import_mode
        job.metadata = metadata
        job.status = DataTransferStatus.DONE
        job.error_message = ''
        job.save(update_fields=['status', 'error_message', 'metadata', 'updated_at'])
        return {'status': DataTransferStatus.DONE}
    except Exception as exc:
        job.status = DataTransferStatus.FAILED
        job.error_message = str(exc)
        job.save(update_fields=['status', 'error_message', 'updated_at'])
        return {'status': DataTransferStatus.FAILED}


@shared_task(name="tracking.heartbeat")
def heartbeat() -> dict[str, str]:
    now = timezone.now().isoformat()
    return {"status": "ok", "timestamp": now}


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
            import json
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

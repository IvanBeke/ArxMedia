import logging
from datetime import datetime
from typing import Any

from django.utils import timezone
from media.models import Movie, Season, TVShow

from ..choices import DataImportMode, MediaType, TvShowStatus, WatchEntryMediaType
from ..models import DataTransferJob, Rating, UserTvShowStatus, WatchEntry, Watchlist
from .system import sync_tmdb_metadata_item

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
    normalized = f'{value[:-1]}+00:00' if value.endswith('Z') else value
    try:
        dt = datetime.fromisoformat(normalized)
    except Exception:
        return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _update_job_progress(job: DataTransferJob, save_every: int = 25):
    if job.processed_items % save_every == 0:
        job.save(update_fields=['total_items', 'processed_items', 'metadata', 'updated_at'])


def _watch_entry_key(media_type: str, tmdb_id: int, season_number: int | None = None, episode_number: int | None = None):
    return (media_type, int(tmdb_id), season_number, episode_number)


def _watchlist_key(media_type: str, tmdb_id: int):
    return (media_type, int(tmdb_id))


def _rating_key(media_type: str, tmdb_id: int):
    return (media_type, int(tmdb_id))


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
            'watched_at': watched_at,
        },
    )
    if created:
        return 'created'

    new_watched_at = watched_at if watched_at else entry.watched_at
    if entry.watched_at and watched_at:
        new_watched_at = max(entry.watched_at, watched_at)

    needs_update = new_watched_at != entry.watched_at
    if needs_update:
        entry.watched_at = new_watched_at
        entry.save(update_fields=['watched_at'])
        return 'updated'
    return 'unchanged'


def _import_watch_entry_status_by_mode(
    user,
    media_type: str,
    tmdb_id: int,
    status_value: str,
    watched_at,
    import_mode: str,
    season_number: int | None = None,
    episode_number: int | None = None,
) -> bool:
    if status_value != TvShowStatus.WATCHED:
        return False

    existing = WatchEntry.objects.filter(
        user=user,
        media_type=media_type,
        tmdb_id=tmdb_id,
        season_number=season_number,
        episode_number=episode_number,
    ).first()
    if existing and import_mode == DataImportMode.NEW_ITEMS:
        return False

    if not existing:
        WatchEntry.objects.create(
            user=user,
            media_type=media_type,
            tmdb_id=tmdb_id,
            season_number=season_number,
            episode_number=episode_number,
            watched_at=watched_at,
        )
        return True

    update_fields = []
    if watched_at:
        if existing.watched_at:
            next_watched_at = max(existing.watched_at, watched_at)
        else:
            next_watched_at = watched_at
        if next_watched_at != existing.watched_at:
            existing.watched_at = next_watched_at
            update_fields.append('watched_at')

    if not update_fields:
        return False

    existing.save(update_fields=update_fields)
    return True


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


def _import_tv_status_by_mode(user, tmdb_id: int, status_value: str, status_at, progress: int | None, import_mode: str) -> bool:
    existing = UserTvShowStatus.objects.filter(user=user, tmdb_id=tmdb_id).first()
    if existing and import_mode == DataImportMode.NEW_ITEMS:
        return False

    payload: dict[str, Any] = {'status': status_value}
    if status_value == TvShowStatus.WATCHED:
        payload['completed_at'] = status_at
    elif status_value == TvShowStatus.PLAN_TO_WATCH:
        payload['plan_to_watch_at'] = status_at
    elif status_value == TvShowStatus.DROPPED:
        payload['dropped_at'] = status_at

    if status_value in (TvShowStatus.WATCHING, TvShowStatus.WATCHED):
        payload['last_watched_at'] = status_at
        if existing is None:
            payload['started_at'] = status_at

    payload['status_changed_at'] = status_at
    if progress is not None:
        payload['watched_episodes'] = progress

    if existing is None:
        defaults = {
            'status': status_value,
            'watched_episodes': progress or 0,
            'total_episodes': 0,
            'progress_percent': 0,
            'started_at': status_at if status_value in (TvShowStatus.WATCHING, TvShowStatus.WATCHED) else None,
            'completed_at': status_at if status_value == TvShowStatus.WATCHED else None,
            'dropped_at': status_at if status_value == TvShowStatus.DROPPED else None,
            'plan_to_watch_at': status_at if status_value == TvShowStatus.PLAN_TO_WATCH else None,
            'last_watched_at': status_at if status_value in (TvShowStatus.WATCHING, TvShowStatus.WATCHED) else None,
            'status_changed_at': status_at,
        }
        UserTvShowStatus.objects.create(user=user, tmdb_id=tmdb_id, **defaults)
        return True

    changed = False
    for key, value in payload.items():
        if getattr(existing, key) != value:
            setattr(existing, key, value)
            changed = True
    if changed:
        existing.save(update_fields=list(payload.keys()))
    return changed


def _mark_show_dropped(user, tmdb_id: int):
    dropped_at = timezone.now()
    show_status, _ = UserTvShowStatus.objects.get_or_create(
        user=user,
        tmdb_id=tmdb_id,
        defaults={'status': TvShowStatus.NONE},
    )
    show_status.status = TvShowStatus.DROPPED
    show_status.dropped_at = dropped_at
    show_status.status_changed_at = dropped_at
    show_status.save(update_fields=['status', 'dropped_at', 'status_changed_at', 'updated_at'])


def _apply_mirror_deletions(job: DataTransferJob, imported_keys: dict, collections_present: set[str]):
    if 'watch_history' in collections_present:
        delete_ids = []
        for entry in WatchEntry.objects.filter(user=job.user):
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
        for rating_item in Rating.objects.filter(user=job.user):
            key = _rating_key(rating_item.media_type, rating_item.tmdb_id)
            if key not in imported_keys['ratings']:
                delete_ids.append(rating_item.id)
        if delete_ids:
            Rating.objects.filter(id__in=delete_ids).delete()


def _ensure_tmdb_metadata(media_type: str, tmdb_id: int | None) -> bool:
    if not tmdb_id:
        return False

    try:
        if media_type not in (MediaType.MOVIE, MediaType.TV, WatchEntryMediaType.EPISODE):
            return False

        sync_tmdb_metadata_item.delay(str(media_type), int(tmdb_id))
        return True
    except Exception as exc:
        logger.warning('Failed metadata sync enqueue for %s %s: %s', media_type, tmdb_id, exc)
        return False


def _has_tmdb_metadata(media_type: str, tmdb_id: int | None, season_number: int | None = None) -> bool:
    if not tmdb_id:
        return False
    if media_type == MediaType.MOVIE:
        return Movie.objects.filter(tmdb_id=int(tmdb_id)).exists()
    if media_type == MediaType.TV:
        return TVShow.objects.filter(tmdb_id=int(tmdb_id)).exists()
    if media_type == WatchEntryMediaType.EPISODE:
        filters: dict[str, int] = {'show__tmdb_id': int(tmdb_id)}
        if season_number is not None:
            filters['season_number'] = season_number
        return Season.objects.filter(**filters).exists()
    return False


def _ensure_tmdb_metadata_for_import_item(media_type: str, tmdb_id: int | None, state: dict, season_number: int | None = None):
    if not tmdb_id:
        return

    key_media_type = MediaType.TV if media_type in (MediaType.TV, WatchEntryMediaType.EPISODE) else media_type
    key = (key_media_type, tmdb_id)
    if key not in state['metadata_checked']:
        if _has_tmdb_metadata(media_type, tmdb_id, season_number=season_number):
            state['metadata_hits'] += 1
        else:
            if _ensure_tmdb_metadata(media_type, tmdb_id):
                state['metadata_fetches'] += 1
            else:
                state['metadata_errors'] += 1
        state['metadata_checked'].add(key)

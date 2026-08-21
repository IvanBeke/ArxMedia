import logging
from datetime import date, timedelta

from celery import shared_task
from django.utils import timezone
from media.models import Movie, TVShow
from media.tmdb import TMDBNotFoundError, tmdb

from ..choices import MediaType, WatchEntryMediaType
from ..status_sync import refresh_show_status

logger = logging.getLogger(__name__)


def _fetch_changed_tmdb_ids(fetch_page) -> set[int]:
    changed_ids: set[int] = set()
    page = 1
    total_pages = 1

    while page <= total_pages:
        payload = fetch_page(page) or {}
        for item in payload.get('results', []):
            tmdb_id = item.get('id')
            if isinstance(tmdb_id, int):
                changed_ids.add(tmdb_id)

        total_pages = int(payload.get('total_pages') or 1)
        page += 1

    return changed_ids


@shared_task(name="tracking.heartbeat")
def heartbeat() -> dict[str, str]:
    now = timezone.now().isoformat()
    return {"status": "ok", "timestamp": now}


@shared_task(name='tracking.sync_tmdb_changed_items')
def sync_tmdb_changed_items() -> dict[str, int | str]:
    end_date = timezone.localdate()
    start_date = end_date - timedelta(days=1)
    return sync_tmdb_changed_items_for_window(start_date, end_date)


@shared_task(name='tracking.refresh_show_status_for_user')
def refresh_show_status_for_user(tmdb_id: int, user_id: int) -> dict[str, int]:
    refresh_show_status(user_id, tmdb_id)
    return {
        'tmdb_id': tmdb_id,
        'user_id': user_id,
    }


@shared_task(name='tracking.sync_tmdb_metadata_item')
def sync_tmdb_metadata_item(media_type: str, tmdb_id: int) -> dict[str, int | str]:
    try:
        if media_type == MediaType.MOVIE:
            tmdb.sync_movie(int(tmdb_id))
        elif media_type in {MediaType.TV, WatchEntryMediaType.EPISODE}:
            tmdb.sync_tv_show(int(tmdb_id), sync_credits=False)
        else:
            return {
                'status': 'skipped',
                'media_type': media_type,
                'tmdb_id': int(tmdb_id),
            }

        return {
            'status': 'ok',
            'media_type': media_type,
            'tmdb_id': int(tmdb_id),
        }
    except TMDBNotFoundError:
        logger.info('TMDB metadata not found for %s %s; skipping.', media_type, tmdb_id)
        return {
            'status': 'not_found',
            'media_type': media_type,
            'tmdb_id': int(tmdb_id),
        }


def sync_tmdb_changed_items_for_window(start_date: date, end_date: date) -> dict[str, int | str]:
    start_date_str = start_date.isoformat()
    end_date_str = end_date.isoformat()

    movie_changed_ids = _fetch_changed_tmdb_ids(
        lambda page: tmdb.get_movie_changes(start_date_str, end_date_str, page=page, use_cache=False)
    )
    tv_changed_ids = _fetch_changed_tmdb_ids(
        lambda page: tmdb.get_tv_changes(start_date_str, end_date_str, page=page, use_cache=False)
    )

    local_movie_ids = set(Movie.objects.filter(tmdb_id__in=movie_changed_ids).values_list('tmdb_id', flat=True))
    local_tv_ids = set(TVShow.objects.filter(tmdb_id__in=tv_changed_ids).values_list('tmdb_id', flat=True))

    movies_synced = 0
    movie_failures = 0
    for tmdb_id in local_movie_ids:
        try:
            tmdb.sync_movie(tmdb_id)
            movies_synced += 1
        except Exception:
            movie_failures += 1

    tv_synced = 0
    tv_failures = 0
    seasons_synced = 0
    season_failures = 0
    episode_credits_synced = 0
    episode_credit_failures = 0
    for tmdb_id in local_tv_ids:
        try:
            show = tmdb.sync_tv_show(tmdb_id)
            tv_synced += 1
            seasons_synced += show.seasons.count()
        except Exception:
            tv_failures += 1
            continue

        for season in show.seasons.all():
            season_number = int(season.season_number)
            for episode_number in season.episodes.values_list('episode_number', flat=True):
                try:
                    tmdb.sync_episode_credits(tmdb_id, season_number, int(episode_number), show=show)
                    episode_credits_synced += 1
                except Exception:
                    episode_credit_failures += 1

    return {
        'window_start': start_date_str,
        'window_end': end_date_str,
        'movie_changed_total': len(movie_changed_ids),
        'tv_changed_total': len(tv_changed_ids),
        'local_movies_matched': len(local_movie_ids),
        'local_tv_matched': len(local_tv_ids),
        'movies_synced': movies_synced,
        'movie_failures': movie_failures,
        'tv_synced': tv_synced,
        'tv_failures': tv_failures,
        'seasons_synced': seasons_synced,
        'season_failures': season_failures,
        'episode_credits_synced': episode_credits_synced,
        'episode_credit_failures': episode_credit_failures,
    }

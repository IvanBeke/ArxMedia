from django.db.models import Count, DateTimeField, Max, Min
from django.db.models.functions import Coalesce
from media.models import Episode, TVShow

from .choices import MediaType, SeasonStatus, TvShowStatus, WatchEntryMediaType
from .models import Rating, UserMediaStatus, WatchEntry

FINAL_TV_STATUSES = {'ended', 'canceled', 'cancelled'}


def _percent(watched_count: int, total_count: int) -> int:
    if total_count <= 0:
        return 0
    return round((watched_count / total_count) * 100)


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _resolve_movie_status(show_status_row, watched_at):
    if show_status_row:
        return show_status_row['status'], show_status_row['status_changed_at']
    if watched_at:
        return TvShowStatus.WATCHED, watched_at
    return None, None


def _build_tv_result_from_status_row(show_status, rating_data):
    return {
        'status': show_status['status'],
        'status_changed_at': show_status['status_changed_at'],
        'watched_at': show_status['last_watched_at'],
        'rating': rating_data.get('rating'),
        'rated_at': rating_data.get('rated_at'),
        'progress': {
            'watched_episodes': show_status['watched_episodes'],
            'total_episodes': show_status['total_episodes'],
            'percent': show_status['progress_percent'],
        },
    }


def _build_tv_result_without_status(show_status_row, rating_data):
    status_value = show_status_row['status'] if show_status_row else None
    changed_at = show_status_row['status_changed_at'] if show_status_row else None
    return {
        'status': status_value,
        'status_changed_at': changed_at,
        'watched_at': None,
        'rating': None,
        'rated_at': None,
        'progress': {
            'watched_episodes': 0,
            'total_episodes': 0,
            'percent': 0,
        },
    }


def annotate_media_user_status(user, media_items):
    if not user or not user.is_authenticated:
        return {}

    normalized_items = []
    movie_ids = set()
    tv_ids = set()
    for item in media_items:
        media_type = item.get('media_type')
        tmdb_id = _as_int(item.get('tmdb_id'))
        if media_type not in (MediaType.MOVIE, MediaType.TV) or tmdb_id is None:
            continue
        normalized_items.append((media_type, tmdb_id))
        if media_type == MediaType.MOVIE:
            movie_ids.add(tmdb_id)
        else:
            tv_ids.add(tmdb_id)

    if not normalized_items:
        return {}

    rating_rows = Rating.objects.filter(
        user=user,
        media_type__in=(MediaType.MOVIE, MediaType.TV),
        tmdb_id__in=movie_ids | tv_ids,
    ).values('media_type', 'tmdb_id', 'score', 'updated_at')
    rating_map = {
        (row['media_type'], row['tmdb_id']): {
            'rating': row['score'],
            'rated_at': row['updated_at'],
        }
        for row in rating_rows
    }

    movie_status_rows = UserMediaStatus.objects.for_user(user).movies().filter(
        tmdb_id__in=movie_ids,
    ).values('tmdb_id', 'status', 'status_changed_at', 'last_watched_at')
    movie_status_map = {row['tmdb_id']: row for row in movie_status_rows}

    tv_status_rows = UserMediaStatus.objects.for_user(user).shows().filter(
        tmdb_id__in=tv_ids,
    ).values('tmdb_id', 'status', 'status_changed_at', 'last_watched_at', 'watched_episodes', 'total_episodes', 'progress_percent')
    tv_status_map = {row['tmdb_id']: row for row in tv_status_rows}

    movie_watched_rows = WatchEntry.objects.filter(
        user=user,
        media_type=WatchEntryMediaType.MOVIE,
        tmdb_id__in=movie_ids,
    ).annotate(
        event_at=Coalesce('watched_at', 'created_at', output_field=DateTimeField())
    ).values('tmdb_id').annotate(last_watched_at=Max('event_at'))
    movie_watched_map = {row['tmdb_id']: row['last_watched_at'] for row in movie_watched_rows}

    result = {}
    for media_type, tmdb_id in normalized_items:
        rating_data = rating_map.get((media_type, tmdb_id), {})
        if media_type == MediaType.MOVIE:
            show_status = movie_status_map.get(tmdb_id)
            watched_at = movie_watched_map.get(tmdb_id)
            status, status_changed_at = _resolve_movie_status(show_status, watched_at)

            result[(media_type, tmdb_id)] = {
                'status': status,
                'status_changed_at': status_changed_at,
                'watched_at': watched_at if status == TvShowStatus.WATCHED else None,
                'rating': rating_data.get('rating'),
                'rated_at': rating_data.get('rated_at'),
            }
            continue

        show_status = tv_status_map.get(tmdb_id)
        if show_status and show_status['status'] != TvShowStatus.PLAN_TO_WATCH:
            result[(media_type, tmdb_id)] = _build_tv_result_from_status_row(show_status, rating_data)
        else:
            result[(media_type, tmdb_id)] = _build_tv_result_without_status(show_status, rating_data)

    return result


def annotate_season_user_status(user, season_items):
    if not user or not user.is_authenticated:
        return {}

    normalized_items = []
    for item in season_items:
        tmdb_id = _as_int(item.get('tmdb_id'))
        season_number = _as_int(item.get('season_number'))
        if tmdb_id is None or season_number is None:
            continue
        normalized_items.append((tmdb_id, season_number))

    if not normalized_items:
        return {}

    tmdb_ids = {tmdb_id for tmdb_id, _ in normalized_items}
    season_numbers = {season_number for _, season_number in normalized_items}

    watched_rows = WatchEntry.objects.filter(
        user=user,
        media_type=WatchEntryMediaType.EPISODE,
        tmdb_id__in=tmdb_ids,
        season_number__in=season_numbers,
    ).annotate(
        event_at=Coalesce('watched_at', 'created_at', output_field=DateTimeField())
    ).values(
        'tmdb_id',
        'season_number',
    ).annotate(
        watched_episodes=Count('id'),
        first_watched_at=Min('event_at'),
        last_watched_at=Max('event_at'),
    )
    watched_map = {(row['tmdb_id'], row['season_number']): row for row in watched_rows}

    total_rows = Episode.objects.filter(
        season__show__tmdb_id__in=tmdb_ids,
        season__season_number__in=season_numbers,
    ).values(
        'season__show__tmdb_id',
        'season__season_number',
    ).annotate(
        total_episodes=Count('id')
    )
    total_map = {
        (row['season__show__tmdb_id'], row['season__season_number']): row['total_episodes']
        for row in total_rows
    }

    final_show_ids = {
        tmdb_id
        for tmdb_id, status in TVShow.objects.filter(tmdb_id__in=tmdb_ids).values_list('tmdb_id', 'status')
        if (status or '').strip().lower() in FINAL_TV_STATUSES
    }

    result = {}
    for key in normalized_items:
        watched_data = watched_map.get(key)
        watched_episodes = watched_data['watched_episodes'] if watched_data else 0
        last_watched_at = watched_data['last_watched_at'] if watched_data else None
        total_episodes = total_map.get(key, 0)
        is_final = key[0] in final_show_ids

        if watched_episodes > 0:
            if (total_episodes == 0 and is_final) or (watched_episodes >= total_episodes and is_final):
                status_value = SeasonStatus.WATCHED
            else:
                status_value = SeasonStatus.WATCHING
            status_changed_at = last_watched_at
        else:
            status_value = None
            status_changed_at = None

        result[key] = {
            'status': status_value,
            'status_changed_at': status_changed_at,
            'watched_at': last_watched_at,
            'rating': None,
            'rated_at': None,
            'progress': {
                'watched_episodes': watched_episodes,
                'total_episodes': total_episodes,
                'percent': _percent(watched_episodes, total_episodes),
            },
        }

    return result

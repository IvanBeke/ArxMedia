from django.db.models import DateTimeField, Max
from django.db.models.functions import Coalesce

from .choices import MediaType, SeasonStatus, TvShowStatus
from .choices import WatchEntryMediaType, WatchEntryStatus
from .models import Rating, UserSeasonStatus, UserTvShowStatus, WatchEntry, Watchlist


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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

    watchlist_rows = Watchlist.objects.filter(
        user=user,
        media_type=MediaType.MOVIE,
        tmdb_id__in=movie_ids,
    ).values('tmdb_id', 'added_at')
    movie_watchlist_map = {row['tmdb_id']: row['added_at'] for row in watchlist_rows}

    tv_watchlist_rows = Watchlist.objects.filter(
        user=user,
        media_type=MediaType.TV,
        tmdb_id__in=tv_ids,
    ).values('tmdb_id', 'added_at')
    tv_watchlist_map = {row['tmdb_id']: row['added_at'] for row in tv_watchlist_rows}

    movie_watched_rows = WatchEntry.objects.filter(
        user=user,
        media_type=WatchEntryMediaType.MOVIE,
        status=WatchEntryStatus.WATCHED,
        tmdb_id__in=movie_ids,
    ).annotate(
        event_at=Coalesce('watched_at', 'created_at', output_field=DateTimeField())
    ).values('tmdb_id').annotate(last_watched_at=Max('event_at'))
    movie_watched_map = {row['tmdb_id']: row['last_watched_at'] for row in movie_watched_rows}

    show_rows = UserTvShowStatus.objects.filter(
        user=user,
        tmdb_id__in=tv_ids,
    ).values(
        'tmdb_id',
        'status',
        'status_changed_at',
        'last_watched_at',
        'watched_episodes',
        'total_episodes',
        'progress_percent',
    )
    show_map = {row['tmdb_id']: row for row in show_rows}

    result = {}
    for media_type, tmdb_id in normalized_items:
        rating_data = rating_map.get((media_type, tmdb_id), {})
        if media_type == MediaType.MOVIE:
            watched_at = movie_watched_map.get(tmdb_id)
            plan_to_watch_at = movie_watchlist_map.get(tmdb_id)
            if watched_at:
                status = TvShowStatus.WATCHED
                status_changed_at = watched_at
            elif plan_to_watch_at:
                status = TvShowStatus.PLAN_TO_WATCH
                status_changed_at = plan_to_watch_at
            else:
                status = TvShowStatus.NONE
                status_changed_at = None

            result[(media_type, tmdb_id)] = {
                'status': status,
                'status_changed_at': status_changed_at,
                'watched_at': watched_at,
                'rating': rating_data.get('rating'),
                'rated_at': rating_data.get('rated_at'),
            }
            continue

        show_status = show_map.get(tmdb_id)
        if show_status:
            result[(media_type, tmdb_id)] = {
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
        else:
            plan_to_watch_at = tv_watchlist_map.get(tmdb_id)
            result[(media_type, tmdb_id)] = {
                'status': TvShowStatus.PLAN_TO_WATCH if plan_to_watch_at else TvShowStatus.NONE,
                'status_changed_at': plan_to_watch_at,
                'watched_at': None,
                'rating': rating_data.get('rating'),
                'rated_at': rating_data.get('rated_at'),
                'progress': {
                    'watched_episodes': 0,
                    'total_episodes': 0,
                    'percent': 0,
                },
            }

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

    season_rows = UserSeasonStatus.objects.filter(
        user=user,
        tmdb_id__in=tmdb_ids,
        season_number__in=season_numbers,
    ).values(
        'tmdb_id',
        'season_number',
        'status',
        'status_changed_at',
        'last_watched_at',
        'watched_episodes',
        'total_episodes',
        'progress_percent',
    )
    season_map = {(row['tmdb_id'], row['season_number']): row for row in season_rows}

    result = {}
    for key in normalized_items:
        season_status = season_map.get(key)
        if season_status:
            result[key] = {
                'status': season_status['status'],
                'status_changed_at': season_status['status_changed_at'],
                'watched_at': season_status['last_watched_at'],
                'rating': None,
                'rated_at': None,
                'progress': {
                    'watched_episodes': season_status['watched_episodes'],
                    'total_episodes': season_status['total_episodes'],
                    'percent': season_status['progress_percent'],
                },
            }
        else:
            result[key] = {
                'status': SeasonStatus.NONE,
                'status_changed_at': None,
                'watched_at': None,
                'rating': None,
                'rated_at': None,
                'progress': {
                    'watched_episodes': 0,
                    'total_episodes': 0,
                    'percent': 0,
                },
            }

    return result

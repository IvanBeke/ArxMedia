from django.db.models import Count, Max

from media.models import Episode, TVShow

from .choices import MediaType, SeasonStatus, TvShowStatus
from .models import Rating, UserMediaStatus, WatchEntry


def _percent(watched_count: int, total_count: int) -> int:
    if total_count <= 0:
        return 0
    return min(100, watched_count * 100 // total_count)


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


def _build_tv_result_without_status(show_status_row, rating_data, total_episodes):
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
            'total_episodes': total_episodes,
            'percent': 0,
        },
    }


def annotate_media_user_status(user, media_items):
    if not user or not user.is_authenticated:
        return {}

    normalized_items, movie_ids, tv_ids = _normalize_media_items(media_items)
    if not normalized_items:
        return {}

    maps = _status_maps(user, movie_ids, tv_ids)
    results = {}
    for media_type, tmdb_id in normalized_items:
        results[(media_type, tmdb_id)] = _media_status_result(media_type, tmdb_id, maps)
    return results


def _media_status_result(media_type, tmdb_id, maps):
    rating_data = maps['ratings'].get((media_type, tmdb_id), {})
    if media_type == MediaType.MOVIE:
        return _movie_status_result(tmdb_id, maps['movie_status'], maps['movie_watched'], rating_data)
    return _tv_status_result(tmdb_id, maps['tv_status'], maps['tv_released_totals'], rating_data)


def _status_maps(user, movie_ids, tv_ids):
    """All per-user status/rating lookups in one place, batched by media type."""
    tv_status = _tv_status_map(user, tv_ids)
    return {
        'ratings': _rating_map(user, movie_ids, tv_ids),
        'movie_status': _movie_status_map(user, movie_ids),
        'movie_watched': _movie_watched_map(user, movie_ids),
        'tv_status': tv_status,
        'tv_released_totals': _tv_released_totals(
            {tmdb_id for tmdb_id in tv_ids if not _has_progress(tv_status.get(tmdb_id))}
        ),
    }


def _normalize_media_items(media_items):
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
    return normalized_items, movie_ids, tv_ids


def _rating_map(user, movie_ids, tv_ids):
    rating_rows = Rating.objects.filter(
        user=user,
        media_type__in=(MediaType.MOVIE, MediaType.TV),
        tmdb_id__in=movie_ids | tv_ids,
    ).values('media_type', 'tmdb_id', 'score', 'updated_at')
    return {
        (row['media_type'], row['tmdb_id']): {
            'rating': row['score'],
            'rated_at': row['updated_at'],
        }
        for row in rating_rows
    }


def _movie_status_result(tmdb_id, movie_status_map, movie_watched_map, rating_data):
    show_status = movie_status_map.get(tmdb_id)
    watched_at = movie_watched_map.get(tmdb_id)
    status, status_changed_at = _resolve_movie_status(show_status, watched_at)

    # Mirror the TV rule below: ratings are only reported for items
    # with a status row that isn't plan_to_watch.
    rated = show_status is not None and show_status['status'] != TvShowStatus.PLAN_TO_WATCH
    return {
        'status': status,
        'status_changed_at': status_changed_at,
        'watched_at': watched_at if status == TvShowStatus.WATCHED else None,
        'rating': rating_data.get('rating') if rated else None,
        'rated_at': rating_data.get('rated_at') if rated else None,
    }


def _movie_status_map(user, movie_ids):
    movie_status_rows = UserMediaStatus.objects.for_user(user).movies().filter(
        tmdb_id__in=movie_ids,
    ).values('tmdb_id', 'status', 'status_changed_at', 'last_watched_at')
    return {row['tmdb_id']: row for row in movie_status_rows}


def _movie_watched_map(user, movie_ids):
    movie_watched_rows = WatchEntry.objects.for_user(user).movies().filter(
        tmdb_id__in=movie_ids,
    ).values('tmdb_id').annotate(last_watched_at=Max('watched_at'))
    return {row['tmdb_id']: row['last_watched_at'] for row in movie_watched_rows}


def _tv_status_map(user, tv_ids):
    tv_status_rows = UserMediaStatus.objects.for_user(user).shows().filter(
        tmdb_id__in=tv_ids,
    ).values('tmdb_id', 'status', 'status_changed_at', 'last_watched_at', 'watched_episodes', 'total_episodes', 'progress_percent')
    return {row['tmdb_id']: row for row in tv_status_rows}


def _has_progress(show_status_row) -> bool:
    return bool(show_status_row) and show_status_row['status'] != TvShowStatus.PLAN_TO_WATCH


def _tv_released_totals(tmdb_ids):
    if not tmdb_ids:
        return {}
    rows = Episode.objects.filter(
        season__show__tmdb_id__in=tmdb_ids,
    ).filter(Episode.released_q()).values('season__show__tmdb_id').annotate(total=Count('id'))
    return {row['season__show__tmdb_id']: row['total'] for row in rows}


def _tv_status_result(tmdb_id, tv_status_map, released_totals, rating_data):
    show_status = tv_status_map.get(tmdb_id)
    if _has_progress(show_status):
        return _build_tv_result_from_status_row(show_status, rating_data)
    return _build_tv_result_without_status(show_status, rating_data, released_totals.get(tmdb_id, 0))


def annotate_season_user_status(user, season_items):
    if not user or not user.is_authenticated:
        return {}

    normalized_items = _normalize_season_items(season_items)
    if not normalized_items:
        return {}

    watched_map, total_map, final_show_ids = _season_contexts(user, normalized_items)

    result = {}
    for key in normalized_items:
        result[key] = _season_status_result(key, watched_map, total_map, final_show_ids)
    return result


def _season_status_result(key, watched_map, total_map, final_show_ids):
    watched_data = watched_map.get(key)
    watched_episodes = watched_data['watched_episodes'] if watched_data else 0
    last_watched_at = watched_data['last_watched_at'] if watched_data else None
    total_episodes = total_map.get(key, 0)

    return {
        'status': _season_status(watched_episodes, total_episodes, key[0] in final_show_ids),
        'status_changed_at': last_watched_at if watched_episodes else None,
        'watched_at': last_watched_at,
        'rating': None,
        'rated_at': None,
        'progress': {
            'watched_episodes': watched_episodes,
            'total_episodes': total_episodes,
            'percent': _percent(watched_episodes, total_episodes),
        },
    }


def _season_status(watched_episodes: int, total_episodes: int, is_final: bool):
    if watched_episodes <= 0:
        return None
    if is_final and watched_episodes >= total_episodes:
        return SeasonStatus.WATCHED
    return SeasonStatus.WATCHING


def _normalize_season_items(season_items):
    normalized_items = []
    for item in season_items:
        tmdb_id = _as_int(item.get('tmdb_id'))
        season_number = _as_int(item.get('season_number'))
        if tmdb_id is None or season_number is None:
            continue
        normalized_items.append((tmdb_id, season_number))
    return normalized_items


def _season_contexts(user, normalized_items):
    """Tuple (watched_map, total_map, final_show_ids) shared by all items."""
    tmdb_ids = {tmdb_id for tmdb_id, _ in normalized_items}
    season_numbers = {season_number for _, season_number in normalized_items}

    released_episode_keys = _released_episode_keys(tmdb_ids, season_numbers)
    watched_map = _watched_map(user, tmdb_ids, season_numbers, released_episode_keys)

    total_map: dict[tuple[int, int], int] = {}
    for tmdb_id, season_number, _ in released_episode_keys:
        key = (tmdb_id, season_number)
        total_map[key] = total_map.get(key, 0) + 1

    final_show_ids = _final_show_ids(tmdb_ids)
    return watched_map, total_map, final_show_ids


def _released_episode_keys(tmdb_ids, season_numbers):
    return set(
        Episode.objects.filter(
            season__show__tmdb_id__in=tmdb_ids,
            season__season_number__in=season_numbers,
        ).filter(Episode.released_q(include_specials=True)).values_list(
            'season__show__tmdb_id', 'season__season_number', 'episode_number'
        )
    )


def _watched_map(user, tmdb_ids, season_numbers, released_episode_keys):
    """Per-season watched count limited to released episodes; last_watched_at covers every watch."""
    watched_rows = WatchEntry.objects.for_user(user).episodes().filter(
        tmdb_id__in=tmdb_ids,
        season_number__in=season_numbers,
    ).values_list('tmdb_id', 'season_number', 'episode_number', 'watched_at')
    watched_map: dict[tuple[int, int], dict] = {}
    for tmdb_id, season_number, episode_number, watched_at in watched_rows:
        entry = watched_map.setdefault((tmdb_id, season_number), {'watched_episodes': 0, 'last_watched_at': None})
        if (tmdb_id, season_number, episode_number) in released_episode_keys:
            entry['watched_episodes'] += 1
        if watched_at and (entry['last_watched_at'] is None or watched_at > entry['last_watched_at']):
            entry['last_watched_at'] = watched_at
    return watched_map


def _final_show_ids(tmdb_ids):
    return {
        tmdb_id
        for tmdb_id, status in TVShow.objects.filter(tmdb_id__in=tmdb_ids).values_list('tmdb_id', 'status')
        if (status or '').strip().lower() in TVShow.FINAL_STATUSES
    }

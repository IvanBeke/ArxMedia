from datetime import date, datetime, timedelta
from datetime import time as dt_time

from django.db.models import (
    Case,
    DateTimeField,
    Exists,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Cast, Coalesce
from django.utils import timezone
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from ..choices import (
    MediaType,
    WatchEntryMediaType,
)
from ..models import (
    Rating,
    UserMediaStatus,
    WatchEntry,
)
from ._helpers import (
    _build_season_map,
    _parse_bool_param,
    _parse_multi_param,
)


def _episode_local_date(episode_or_dict):
    broadcast_start = getattr(episode_or_dict, 'broadcast_start', None)
    if broadcast_start is None and isinstance(episode_or_dict, dict):
        broadcast_start = episode_or_dict.get('broadcast_start')
    if broadcast_start:
        return timezone.localtime(broadcast_start).date()

    air_date = getattr(episode_or_dict, 'air_date', None)
    if air_date is None and isinstance(episode_or_dict, dict):
        air_date = episode_or_dict.get('air_date')
    if air_date is not None:
        return air_date
    return None

def _episode_local_datetime(episode_or_dict):
    broadcast_start = getattr(episode_or_dict, 'broadcast_start', None)
    if broadcast_start is None and isinstance(episode_or_dict, dict):
        broadcast_start = episode_or_dict.get('broadcast_start')
    if broadcast_start:
        return timezone.localtime(broadcast_start)

    air_date = getattr(episode_or_dict, 'air_date', None)
    if air_date is None and isinstance(episode_or_dict, dict):
        air_date = episode_or_dict.get('air_date')
    if air_date is not None:
        return timezone.make_aware(datetime.combine(air_date, dt_time.min), timezone.get_current_timezone())
    return None

def _episode_display_air_date(episode_or_dict):
    broadcast_start = getattr(episode_or_dict, 'broadcast_start', None)
    if broadcast_start is None and isinstance(episode_or_dict, dict):
        broadcast_start = episode_or_dict.get('broadcast_start')
    if broadcast_start:
        return _episode_local_datetime(episode_or_dict)

    air_date = getattr(episode_or_dict, 'air_date', None)
    if air_date is None and isinstance(episode_or_dict, dict):
        air_date = episode_or_dict.get('air_date')
    return air_date

def _episode_schedule_expression():
    return Coalesce('broadcast_start', Cast('air_date', output_field=DateTimeField()))

def _watched_episode_exists(user):
    return WatchEntry.objects.filter(
        user=user,
        media_type=WatchEntryMediaType.EPISODE,
        tmdb_id=OuterRef('season__show__tmdb_id'),
        season_number=OuterRef('season__season_number'),
        episode_number=OuterRef('episode_number'),
    )

def _episode_candidates(user, now, *, aired):
    from media.models import Episode

    episodes = Episode.objects.filter(
        season__show__tmdb_id=OuterRef('tmdb_id'),
    )
    if aired:
        episodes = episodes.filter(Episode.released_q(now)).filter(~Exists(_watched_episode_exists(user)))
    else:
        episodes = episodes.filter(Episode.upcoming_q(now))
    return episodes.annotate(schedule_at=_episode_schedule_expression()).order_by(
        'schedule_at', 'season__season_number', 'episode_number'
    )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def up_next(request):
    """Get next episodes for currently watching shows."""
    from django.utils import timezone
    from media.models import TVShow

    now = timezone.now()
    today = now.date()

    watched_show_ids = UserMediaStatus.objects.for_user(request.user).shows().active().with_watched_episodes().with_next_episode().filter(
        next_episode_id__isnull=False,
    ).annotate(
        unknown_runtime_count=Case(
            When(time_left_has_unknown=True, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ),
    ).values(
        'tmdb_id',
        'last_watched_at',
        'progress_percent',
        'next_season_number',
        'next_episode_number',
        'next_episode_name',
        'next_still_path',
        'next_air_date',
        'next_broadcast_start',
        'next_runtime',
        'next_episode_type',
        'episodes_left',
        'time_left_minutes',
        'unknown_runtime_count',
    ).order_by('-last_watched_at', '-tmdb_id')

    watched_show_rows = list(watched_show_ids)

    shows_by_tmdb_id = {
        show.tmdb_id: show
        for show in TVShow.objects.filter(tmdb_id__in=[item['tmdb_id'] for item in watched_show_rows]).only('tmdb_id', 'name', 'poster_path')
    }

    next_season_map = _build_season_map(
        (item['tmdb_id'], item['next_season_number'])
        for item in watched_show_rows
        if item['next_season_number'] is not None
    )

    up_next_data = []
    new_threshold = today - timedelta(days=7)
    for show_item in watched_show_rows:
        show = shows_by_tmdb_id.get(show_item['tmdb_id'])
        if show is None:
            continue
        progress_percent = show_item.get('progress_percent')
        next_season = next_season_map.get((show_item['tmdb_id'], show_item['next_season_number']))
        next_broadcast_start = show_item.get('next_broadcast_start')
        next_air_date = show_item.get('next_air_date')
        next_episode_local_dt = _episode_local_datetime({'air_date': next_air_date, 'broadcast_start': next_broadcast_start})

        up_next_data.append({
            'tmdb_id': show_item['tmdb_id'],
            'show_name': show.name,
            'poster_path': (next_season.poster_path if next_season else '') or show.poster_path,
            'poster_url': (next_season.poster_url if next_season else None) or show.poster_url,
            'last_watched_at': show_item['last_watched_at'],
            'progress_percent': progress_percent if progress_percent is not None else 0,
            'episodes_left': show_item['episodes_left'],
            'runtime_left_minutes': show_item['time_left_minutes'],
            'runtime_left_has_unknown': show_item['unknown_runtime_count'] > 0,
            'next_episode': {
                'season_number': show_item['next_season_number'],
                'episode_number': show_item['next_episode_number'],
                'name': show_item['next_episode_name'],
                'still_path': show_item['next_still_path'],
                'still_url': f"https://image.tmdb.org/t/p/w300{show_item['next_still_path']}" if show_item['next_still_path'] else None,
                'air_date': _episode_display_air_date({'air_date': next_air_date, 'broadcast_start': next_broadcast_start}),
                'broadcast_start': next_broadcast_start,
                'local_broadcast_datetime': next_episode_local_dt,
                'runtime': show_item['next_runtime'],
                'episode_type': show_item['next_episode_type'],
            }
        })

    new_items = []
    old_items = []
    for item in up_next_data:
        air_date = item.get('next_episode', {}).get('local_broadcast_datetime', item.get('next_episode', {}).get('air_date'))
        if isinstance(air_date, datetime):
            air_date = air_date.date()
        is_new = bool(air_date and new_threshold <= air_date <= today)
        item['is_new'] = is_new
        if is_new:
            new_items.append(item)
        else:
            old_items.append(item)

    new_items.sort(
        key=lambda item: (
            item['next_episode'].get('local_broadcast_datetime') or item['next_episode'].get('air_date') or date.max,
            item['show_name'].lower(),
        ),
        reverse=True,
    )
    ordered_items = new_items + old_items

    for item in ordered_items:
        item.pop('last_watched_at', None)

    return Response(ordered_items)


def _apply_progress_filters(items, request):
    params = request.query_params
    search = (params.get('search') or '').strip().lower()
    provider_status_values = {value.lower() for value in _parse_multi_param(params, 'provider_status')}
    selected_genres = {value.lower() for value in _parse_multi_param(params, 'genres')}
    has_upcoming = _parse_bool_param(params.get('has_upcoming'))
    is_new = _parse_bool_param(params.get('is_new'))
    missing_rating = _parse_bool_param(params.get('missing_rating'))
    has_next_episode = _parse_bool_param(params.get('has_next_episode'))

    filtered = []
    for item in items:
        if search and search not in item['show_name'].lower():
            continue
        if provider_status_values:
            provider_status = str(item.get('provider_status') or '').strip().lower()
            if provider_status not in provider_status_values:
                continue
        if selected_genres:
            item_genres = {genre.lower() for genre in (item.get('genres') or [])}
            if item_genres.isdisjoint(selected_genres):
                continue
        if has_upcoming is not None and item.get('has_upcoming_episode', False) != has_upcoming:
            continue
        if is_new is not None and item.get('is_new', False) != is_new:
            continue
        if missing_rating is True and item['user_rating'] is not None:
            continue
        if missing_rating is True and item.get('status') == 'plan_to_watch':
            continue
        if has_next_episode is not None:
            has_episode = item.get('next_episode') is not None
            if has_episode != has_next_episode:
                continue
        filtered.append(item)
    return filtered


def _annotate_my_shows_episodes(status_queryset, user, now):
    upcoming_episode = _episode_candidates(user, now, aired=False)
    latest_watched_episode = WatchEntry.objects.filter(
        user=user,
        media_type=WatchEntryMediaType.EPISODE,
        tmdb_id=OuterRef('tmdb_id'),
        season_number__isnull=False,
        episode_number__isnull=False,
    ).annotate(
        event_at=Coalesce('watched_at', 'created_at', output_field=DateTimeField())
    ).order_by('-event_at', '-id')
    return status_queryset.with_next_episode().annotate(
        upcoming_season_number=Subquery(upcoming_episode.values('season__season_number')[:1]),
        upcoming_episode_number=Subquery(upcoming_episode.values('episode_number')[:1]),
        upcoming_episode_name=Subquery(upcoming_episode.values('name')[:1]),
        upcoming_episode_type=Subquery(upcoming_episode.values('episode_type')[:1]),
        upcoming_air_date=Subquery(upcoming_episode.values('air_date')[:1]),
        upcoming_broadcast_start=Subquery(upcoming_episode.values('broadcast_start')[:1]),
        last_watched_season_number=Subquery(latest_watched_episode.values('season_number')[:1]),
        last_watched_episode_number=Subquery(latest_watched_episode.values('episode_number')[:1]),
    )


def _attach_my_shows_next_episodes(rows):
    from media.models import Episode

    next_ids = {row['next_episode_id'] for row in rows if row['next_episode_id'] is not None}
    episodes = {
        episode.id: episode
        for episode in Episode.objects.filter(id__in=next_ids).select_related('season')
    }
    for row in rows:
        episode = episodes.get(row['next_episode_id'])
        row.update({
            'next_season_number': episode.season.season_number if episode else None,
            'next_episode_number': episode.episode_number if episode else None,
            'next_episode_name': episode.name if episode else None,
            'next_still_path': episode.still_path if episode else None,
            'next_air_date': episode.air_date if episode else None,
            'next_broadcast_start': episode.broadcast_start if episode else None,
            'next_runtime': episode.runtime if episode else None,
            'next_episode_type': episode.episode_type if episode else None,
            'next_vote_average': episode.vote_average if episode else None,
            'next_vote_count': episode.vote_count if episode else None,
        })
    return rows


def _my_shows_status_rows(user, now, status_queryset):
    rows = list(
        _annotate_my_shows_episodes(status_queryset, user, now).values(
            'tmdb_id', 'status', 'progress_percent', 'last_watched_at', 'started_at',
            'watched_episodes', 'total_episodes', 'episodes_left', 'time_left_minutes',
            'time_left_has_unknown', 'next_episode_id', 'upcoming_season_number', 'upcoming_episode_number',
            'upcoming_episode_name', 'upcoming_episode_type', 'upcoming_air_date',
            'upcoming_broadcast_start', 'last_watched_season_number',
            'last_watched_episode_number',
        )
    )
    return _attach_my_shows_next_episodes(rows)


def _build_my_show_item(tmdb_id, show, row, user_rating, new_threshold, today):
    raw_networks = [part.strip() for part in (show.networks or '').split(',') if part.strip()]
    next_air_date = row.get('next_air_date')
    next_broadcast_start = row.get('next_broadcast_start')
    next_local_air_date = _episode_local_date({'air_date': next_air_date, 'broadcast_start': next_broadcast_start})
    is_new = bool(next_local_air_date and new_threshold <= next_local_air_date <= today)
    item = {
        'tmdb_id': tmdb_id,
        'show_name': show.name,
        'release_date': show.first_air_date,
        'poster_path': show.poster_path,
        'poster_url': show.poster_url,
        'number_of_seasons': show.number_of_seasons,
        'status': row['status'],
        'provider_status': show.status,
        'user_rating': user_rating,
        'vote_average': show.vote_average,
        'vote_count': show.vote_count,
        'genres': [genre.name for genre in show.genres.all()],
        'networks': raw_networks,
        'episode_runtime': show.episode_runtime,
    }
    upcoming_local_air_date = _episode_local_date({'air_date': row.get('upcoming_air_date'), 'broadcast_start': row.get('upcoming_broadcast_start')})
    next_episode = None
    if row['next_episode_id'] is not None:
        next_episode = {
            'season_number': row['next_season_number'],
            'episode_number': row['next_episode_number'],
            'name': row['next_episode_name'],
            'still_path': row['next_still_path'],
            'still_url': f"https://image.tmdb.org/t/p/w300{row['next_still_path']}" if row['next_still_path'] else None,
            'air_date': _episode_display_air_date({'air_date': row['next_air_date'], 'broadcast_start': row['next_broadcast_start']}),
            'broadcast_start': row['next_broadcast_start'],
            'local_broadcast_datetime': _episode_local_datetime({'air_date': row['next_air_date'], 'broadcast_start': row['next_broadcast_start']}),
            'runtime': row['next_runtime'],
            'episode_type': row['next_episode_type'],
            'vote_average': row['next_vote_average'],
            'vote_count': row['next_vote_count'],
        }
    item.update({
        'progress_percent': row['progress_percent'] or 0,
        'watched_episodes': row['watched_episodes'] or 0,
        'total_episodes': row['total_episodes'] or 0,
        'last_watched_at': row['last_watched_at'],
        'started_at': row['started_at'],
        'episodes_left': row['episodes_left'],
        'runtime_left_minutes': row['time_left_minutes'],
        'runtime_left_has_unknown': row['time_left_has_unknown'],
        'is_new': is_new,
        'has_upcoming_episode': upcoming_local_air_date is not None,
        'next_episode': next_episode,
        'upcoming_episode': {
            'season_number': row['upcoming_season_number'],
            'episode_number': row['upcoming_episode_number'],
            'name': row['upcoming_episode_name'],
            'episode_type': row['upcoming_episode_type'],
            'air_date': _episode_display_air_date({'air_date': row['upcoming_air_date'], 'broadcast_start': row['upcoming_broadcast_start']}),
            'broadcast_start': row['upcoming_broadcast_start'],
            'local_broadcast_datetime': _episode_local_datetime({'air_date': row['upcoming_air_date'], 'broadcast_start': row['upcoming_broadcast_start']}),
        },
        'last_watched_episode': {
            'season_number': row['last_watched_season_number'],
            'episode_number': row['last_watched_episode_number'],
        },
    })
    return item


def _sort_progress_items(items, sort_by: str, direction: str):
    sort_key = (sort_by or 'last_watched').strip().lower()
    direction_key = (direction or '').strip().lower()
    default_direction_by_sort = {
        'last_watched': 'desc',
        'release_date': 'desc',
        'next_episode_date': 'desc',
        'provider_rating': 'desc',
        'user_rating': 'desc',
    }
    default_direction = default_direction_by_sort.get(sort_key, 'asc')
    final_direction = direction_key if direction_key in ('asc', 'desc') else default_direction

    if sort_key == 'last_watched':
        def watched_ts(item):
            value = item.get('last_watched_at')
            return value.timestamp() if value is not None else None

        if final_direction == 'desc':
            return sorted(
                items,
                key=lambda item: (
                    watched_ts(item) is None,
                    -(watched_ts(item) or 0),
                    item['show_name'].lower(),
                ),
            )
        return sorted(
            items,
            key=lambda item: (
                watched_ts(item) is None,
                watched_ts(item) or 0,
                item['show_name'].lower(),
            ),
        )

    if sort_key == 'progress_percent':
        return sorted(
            items,
            key=lambda item: ((item.get('progress_percent') or 0), item['show_name'].lower()),
            reverse=final_direction == 'desc',
        )

    if sort_key in ('provider_rating', 'user_rating'):
        rating_key = 'vote_average' if sort_key == 'provider_rating' else 'user_rating'
        return sorted(
            items,
            key=lambda item: (
                item.get(rating_key) or 0,
                item['show_name'].lower(),
            ),
            reverse=final_direction == 'desc',
        )

    if sort_key == 'title':
        return sorted(items, key=lambda item: item['show_name'].lower(), reverse=final_direction == 'desc')

    if sort_key == 'next_episode_date':
        return sorted(
            items,
            key=lambda item: (
                (item.get('next_episode') or {}).get('air_date') is None,
                (item.get('next_episode') or {}).get('air_date') or date.max,
                item['show_name'].lower(),
            ),
            reverse=final_direction == 'desc',
        )

    if sort_key == 'release_date':
        return sorted(
            items,
            key=lambda item: (
                item['release_date'] is None,
                item['release_date'] or date.max,
                item['show_name'].lower(),
            ),
            reverse=final_direction == 'desc',
        )

    if sort_key == 'started_date':
        def started_ts(item):
            value = item.get('started_at')
            return value.timestamp() if value is not None else None

        if final_direction == 'desc':
            return sorted(
                items,
                key=lambda item: (
                    started_ts(item) is None,
                    -(started_ts(item) or 0),
                    item['show_name'].lower(),
                ),
            )
        return sorted(
            items,
            key=lambda item: (
                started_ts(item) is None,
                started_ts(item) or 0,
                item['show_name'].lower(),
            ),
        )

    if sort_key == 'episodes_left':
        return sorted(
            items,
            key=lambda item: (
                (item.get('episodes_left') or 0) <= 0,
                (item.get('episodes_left') or 0) if (item.get('episodes_left') or 0) > 0 else 10**9,
                (item.get('runtime_left_minutes') or 0) if (item.get('episodes_left') or 0) > 0 else 10**9,
                item['show_name'].lower(),
            ),
            reverse=final_direction == 'desc',
        )

    return sorted(
        items,
        key=lambda item: (
            (item.get('episodes_left') or 0) <= 0,
            (item.get('runtime_left_minutes') or 0) if (item.get('episodes_left') or 0) > 0 else 10**9,
            (item.get('episodes_left') or 0) if (item.get('episodes_left') or 0) > 0 else 10**9,
            item['show_name'].lower(),
        ),
        reverse=final_direction == 'desc',
    )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def my_shows_list(request):
    from media.models import Episode, TVShow

    today = timezone.now().date()
    now = timezone.now()

    status_queryset = UserMediaStatus.objects.for_user(request.user).shows()
    status_values = {value.lower() for value in _parse_multi_param(request.query_params, 'status')}
    if status_values:
        status_queryset = status_queryset.filter(status__in=status_values)
    progress_tmdb_ids = set(status_queryset.values_list('tmdb_id', flat=True))

    status_rows = _my_shows_status_rows(request.user, now, status_queryset)

    if not progress_tmdb_ids:
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset([], request)
        if page is None:
            return Response({
                'results': [],
                'count': 0,
                'next': None,
                'previous': None,
                'available_genres': [],
                'available_provider_statuses': [],
                'total_runtime_minutes': 0,
            })
        response = paginator.get_paginated_response(page)
        response.data['available_genres'] = []
        response.data['available_provider_statuses'] = []
        response.data['total_runtime_minutes'] = 0
        return response

    status_row_by_tmdb_id = {row['tmdb_id']: row for row in status_rows}
    tmdb_ids = list(progress_tmdb_ids)

    shows = TVShow.objects.filter(tmdb_id__in=tmdb_ids).prefetch_related('genres')
    show_map = {show.tmdb_id: show for show in shows}
    rating_map = {
        row['tmdb_id']: row['score']
        for row in Rating.objects.filter(
            user=request.user,
            media_type=MediaType.TV,
            tmdb_id__in=tmdb_ids,
        ).values('tmdb_id', 'score')
    }

    new_threshold = today - timedelta(days=7)
    progress_items = []
    for tmdb_id in tmdb_ids:
        show = show_map.get(tmdb_id)
        if show is None:
            continue
        row = status_row_by_tmdb_id.get(tmdb_id)
        progress_items.append(_build_my_show_item(tmdb_id, show, row, rating_map.get(tmdb_id), new_threshold, today))

    available_genres = sorted({genre for item in progress_items for genre in item['genres']})
    available_provider_statuses = sorted({
        str(item['provider_status']).strip()
        for item in progress_items
        if str(item.get('provider_status') or '').strip()
    })

    filtered = _apply_progress_filters(progress_items, request)
    sorted_items = _sort_progress_items(filtered, request.query_params.get('sort'), request.query_params.get('direction'))
    filtered_ids = [item['tmdb_id'] for item in filtered]
    total_runtime_by_show = {
        row['season__show__tmdb_id']: row['total'] or 0
        for row in Episode.objects.filter(
            season__show__tmdb_id__in=filtered_ids,
            season__season_number__gt=0,
        ).values('season__show__tmdb_id').annotate(total=Sum('runtime'))
    }
    total_runtime_minutes = sum(total_runtime_by_show.get(tmdb_id, 0) for tmdb_id in filtered_ids)

    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(sorted_items, request)
    if page is None:
        return Response({
            'results': sorted_items,
            'count': len(sorted_items),
            'next': None,
            'previous': None,
            'available_genres': available_genres,
            'available_provider_statuses': available_provider_statuses,
            'total_runtime_minutes': total_runtime_minutes,
        })
    response = paginator.get_paginated_response(page)
    response.data['available_genres'] = available_genres
    response.data['available_provider_statuses'] = available_provider_statuses
    response.data['total_runtime_minutes'] = total_runtime_minutes
    return response


def _apply_movie_filters(items, request):
    params = request.query_params
    search = (params.get('search') or '').strip().lower()
    status_values = {value.lower() for value in _parse_multi_param(params, 'status')}
    selected_genres = {value.lower() for value in _parse_multi_param(params, 'genres')}
    missing_rating = _parse_bool_param(params.get('missing_rating'))

    filtered = []
    for item in items:
        if search and search not in item['title'].lower():
            continue
        if status_values and item['status'] not in status_values:
            continue
        if selected_genres:
            item_genres = {genre.lower() for genre in (item.get('genres') or [])}
            if item_genres.isdisjoint(selected_genres):
                continue
        if missing_rating is True and item['user_rating'] is not None:
            continue
        filtered.append(item)
    return filtered


def _sort_movie_items(items, sort_by: str, direction: str):
    sort_key = (sort_by or 'watched_date').strip().lower()
    direction_key = (direction or '').strip().lower()
    default_direction_by_sort = {
        'provider_rating': 'desc',
        'user_rating': 'desc',
        'release_date': 'desc',
        'watched_date': 'desc',
    }
    final_direction = direction_key if direction_key in ('asc', 'desc') else default_direction_by_sort.get(sort_key, 'asc')

    def title_key(item):
        return item['title'].lower()

    if sort_key == 'release_date':
        return sorted(
            items,
            key=lambda item: (
                item['release_date'] is None,
                item['release_date'] or date.max,
                title_key(item),
            ),
            reverse=final_direction == 'desc',
        )

    if sort_key == 'user_rating':
        def rating_value(item):
            score = item.get('user_rating')
            return -(score or 0) if final_direction == 'desc' else (score or 0)

        return sorted(
            items,
            key=lambda item: (rating_value(item), title_key(item)),
        )

    if sort_key == 'provider_rating':
        return sorted(
            items,
            key=lambda item: (item.get('vote_average') is None, item.get('vote_average') or 0, title_key(item)),
            reverse=final_direction == 'desc',
        )

    if sort_key == 'runtime':
        return sorted(
            items,
            key=lambda item: (
                item.get('runtime') is None,
                item.get('runtime') or 0,
                title_key(item),
            ),
            reverse=final_direction == 'desc',
        )

    if sort_key == 'watched_date':
        def watched_ts(item):
            value = item.get('last_watched_at')
            return value.timestamp() if value is not None else None

        if final_direction == 'desc':
            return sorted(
                items,
                key=lambda item: (watched_ts(item) is None, -(watched_ts(item) or 0), title_key(item)),
            )
        return sorted(
            items,
            key=lambda item: (watched_ts(item) is None, watched_ts(item) or 0, title_key(item)),
        )

    return sorted(items, key=title_key, reverse=final_direction == 'desc')


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def my_movies_list(request):
    from media.models import Movie

    status_rows = list(
        UserMediaStatus.objects.movies().filter(user=request.user).values(
            'tmdb_id',
            'status',
            'last_watched_at',
        )
    )

    if not status_rows:
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset([], request)
        if page is None:
            return Response({
                'results': [],
                'count': 0,
                'next': None,
                'previous': None,
                'available_genres': [],
                'total_runtime_minutes': 0,
            })
        response = paginator.get_paginated_response(page)
        response.data['available_genres'] = []
        response.data['total_runtime_minutes'] = 0
        return response

    status_row_by_tmdb_id = {row['tmdb_id']: row for row in status_rows}
    tmdb_ids = list(status_row_by_tmdb_id)

    movies = Movie.objects.filter(tmdb_id__in=tmdb_ids).prefetch_related('genres')
    movie_map = {movie.tmdb_id: movie for movie in movies}
    rating_map = {
        row['tmdb_id']: row['score']
        for row in Rating.objects.filter(
            user=request.user,
            media_type=MediaType.MOVIE,
            tmdb_id__in=tmdb_ids,
        ).values('tmdb_id', 'score')
    }

    progress_items = []
    for tmdb_id in tmdb_ids:
        movie = movie_map.get(tmdb_id)
        if movie is None:
            continue

        row = status_row_by_tmdb_id[tmdb_id]
        progress_items.append({
            'tmdb_id': tmdb_id,
            'title': movie.title,
            'release_date': movie.release_date,
            'poster_path': movie.poster_path,
            'poster_url': movie.poster_url,
            'runtime': movie.runtime,
            'genres': [genre.name for genre in movie.genres.all()],
            'status': row['status'],
            'user_rating': rating_map.get(tmdb_id),
            'vote_average': movie.vote_average,
            'vote_count': movie.vote_count,
            'last_watched_at': row['last_watched_at'],
        })

    available_genres = sorted({genre for item in progress_items for genre in item['genres']})

    filtered = _apply_movie_filters(progress_items, request)
    sorted_items = _sort_movie_items(filtered, request.query_params.get('sort'), request.query_params.get('direction'))
    total_runtime_minutes = sum(
        item['runtime'] or 0
        for item in filtered
    )

    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(sorted_items, request)
    if page is None:
        return Response({
            'results': sorted_items,
            'count': len(sorted_items),
            'next': None,
            'previous': None,
            'available_genres': available_genres,
            'total_runtime_minutes': total_runtime_minutes,
        })
    response = paginator.get_paginated_response(page)
    response.data['available_genres'] = available_genres
    response.data['total_runtime_minutes'] = total_runtime_minutes
    return response


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def upcoming(request):
    """Get all episodes airing in the next seven calendar days for shows the user is watching."""
    from media.models import Episode

    shows_with_episodes = UserMediaStatus.objects.for_user(request.user).shows().progressable().values_list(
        'tmdb_id', flat=True,
    ).distinct()

    now = timezone.now()
    current_timezone = timezone.get_current_timezone()
    today = now.astimezone(current_timezone).date()
    window_end_date = today + timedelta(days=7)
    window_end = timezone.make_aware(
        datetime.combine(window_end_date, dt_time.min),
        current_timezone,
    )
    all_upcoming = (
        Episode.objects.filter(
            season__show__tmdb_id__in=shows_with_episodes,
        )
        .filter(Episode.regular_q())
        .filter(
            Q(broadcast_start__gt=now, broadcast_start__lt=window_end)
            | Q(
                broadcast_start__isnull=True,
                air_date__gte=today,
                air_date__lt=window_end_date,
            )
        )
        .annotate(schedule_at=_episode_schedule_expression())
        .select_related('season__show')
        .order_by('schedule_at', 'season__show__tmdb_id', 'season__season_number', 'episode_number')
    )

    upcoming_data = [{
        'tmdb_id': ep.season.show.tmdb_id,
        'show_name': ep.season.show.name,
        'poster_path': ep.season.poster_path or ep.season.show.poster_path,
        'poster_url': ep.season.poster_url or ep.season.show.poster_url,
        'season_number': ep.season.season_number,
        'episode_number': ep.episode_number,
        'name': ep.name,
        'episode_type': ep.episode_type,
        'still_path': ep.still_path,
        'still_url': ep.still_url,
        'air_date': ep.display_air_date,
    } for ep in all_upcoming]

    return Response(upcoming_data)

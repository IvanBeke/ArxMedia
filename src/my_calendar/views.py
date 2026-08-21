from datetime import timedelta

from django.utils import timezone
from django.utils.dateparse import parse_date
from media.models import Episode, Movie
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from tracking.choices import TvShowStatus
from tracking.models import UserMediaStatus


def _parse_range(request):
    start_param = request.query_params.get('start')
    days_param = request.query_params.get('days', '30')
    start = parse_date(start_param) if start_param else timezone.localdate()
    try:
        days = int(days_param)
    except (TypeError, ValueError):
        days = 30
    days = max(days, 1)
    days = min(days, 90)
    end = start + timedelta(days=days)
    return start, end


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def shows_calendar(request):
    start, end = _parse_range(request)
    episodes = Episode.objects.select_related('season__show').filter(
        air_date__gte=start,
        air_date__lt=end,
    ).order_by('air_date', 'season__show__name', 'season__season_number', 'episode_number')

    data = []
    for ep in episodes:
        data.append({
            'air_date': ep.air_date,
            'tmdb_id': ep.season.show.tmdb_id,
            'show_name': ep.season.show.name,
            'poster_url': ep.season.show.poster_url,
            'season_number': ep.season.season_number,
            'episode_number': ep.episode_number,
            'episode_name': ep.name,
        })
    return Response({'results': data})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def movies_calendar(request):
    start, end = _parse_range(request)
    movies = Movie.objects.filter(
        release_date__gte=start,
        release_date__lt=end,
    ).order_by('release_date', 'title')

    data = []
    for movie in movies:
        data.append({
            'release_date': movie.release_date,
            'tmdb_id': movie.tmdb_id,
            'title': movie.title,
            'poster_url': movie.poster_url,
        })
    return Response({'results': data})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def my_calendar(request):
    start, end = _parse_range(request)

    watchlist_movie_ids = list(
        UserMediaStatus.objects.for_user(request.user).movies().planning().values_list('tmdb_id', flat=True)
    )
    dropped_tv_ids = list(
        UserMediaStatus.objects.shows().filter(
            user=request.user,
            status=TvShowStatus.DROPPED,
        ).values_list('tmdb_id', flat=True)
    )
    watching_tv_ids = list(
        UserMediaStatus.objects.shows().filter(
            user=request.user,
            status__in=(TvShowStatus.WATCHING, TvShowStatus.WATCHED),
            watched_episodes__gt=0,
        ).exclude(
            tmdb_id__in=dropped_tv_ids,
        ).values_list('tmdb_id', flat=True)
    )

    movies = Movie.objects.filter(tmdb_id__in=watchlist_movie_ids, release_date__gte=start, release_date__lt=end)
    episodes = Episode.objects.select_related('season__show').filter(
        season__show__tmdb_id__in=watching_tv_ids,
        air_date__gte=start,
        air_date__lt=end,
    )

    movie_items = [{
        'kind': 'movie',
        'date': m.release_date,
        'tmdb_id': m.tmdb_id,
        'title': m.title,
        'poster_url': m.poster_url,
    } for m in movies]

    show_items = [{
        'kind': 'episode',
        'date': ep.air_date,
        'tmdb_id': ep.season.show.tmdb_id,
        'show_name': ep.season.show.name,
        'season_number': ep.season.season_number,
        'episode_number': ep.episode_number,
        'episode_name': ep.name,
        'poster_url': ep.season.show.poster_url,
    } for ep in episodes]

    combined = movie_items + show_items
    combined.sort(key=lambda x: (x['date'], x.get('title') or x.get('show_name') or ''))

    return Response({'results': combined})

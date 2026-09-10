from datetime import datetime, time, timedelta

from django.db.models import DateTimeField
from django.db.models.functions import Cast, Coalesce
from django.utils import timezone
from django.utils.dateparse import parse_date
from media.models import Episode, Movie
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
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
def my_calendar(request):
    start, end = _parse_range(request)

    watchlist_movie_ids = list(
        UserMediaStatus.objects.for_user(request.user).movies().planning().values_list('tmdb_id', flat=True)
    )
    dropped_tv_ids = list(UserMediaStatus.objects.for_user(request.user).shows().dropped().values_list('tmdb_id', flat=True))
    watching_tv_ids = list(
        UserMediaStatus.objects.for_user(request.user).shows().progressable().exclude(
            tmdb_id__in=dropped_tv_ids,
        ).values_list('tmdb_id', flat=True)
    )

    movies = Movie.objects.filter(tmdb_id__in=watchlist_movie_ids, release_date__gte=start, release_date__lt=end)
    episodes = Episode.objects.select_related('season__show').annotate(
        schedule_at=Coalesce('broadcast_start', Cast('air_date', output_field=DateTimeField())),
    ).filter(
        season__show__tmdb_id__in=watching_tv_ids,
        schedule_at__gte=timezone.make_aware(datetime.combine(start, time.min), timezone.get_current_timezone()),
        schedule_at__lt=timezone.make_aware(datetime.combine(end, time.min), timezone.get_current_timezone()),
    ).exclude(
        season__season_number=0,
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
        'date': ep.display_air_date,
        'tmdb_id': ep.season.show.tmdb_id,
        'show_name': ep.season.show.name,
        'season_number': ep.season.season_number,
        'episode_number': ep.episode_number,
        'episode_name': ep.name,
        'poster_url': ep.season.show.poster_url,
    } for ep in episodes]

    combined = movie_items + show_items
    combined.sort(
        key=lambda x: (
            x['date'] if isinstance(x['date'], datetime) else datetime.combine(x['date'], time.min),
            x.get('title') or x.get('show_name') or '',
        )
    )

    return Response({'results': combined})

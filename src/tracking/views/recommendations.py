import logging
from typing import Any

from django.db import transaction
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from media.tmdb import tmdb

from ..choices import WatchEntryMediaType
from ..models import (
    UserMediaStatus,
    WatchEntry,
)

logger = logging.getLogger(__name__)


# Calls TMDB and only reads tracking data, so it does not need the request-wide transaction.
@transaction.non_atomic_requests
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def recommendations(request):
    watched_movies = set(
        WatchEntry.objects.filter(
            user=request.user,
            media_type=WatchEntryMediaType.MOVIE,
        ).values_list('tmdb_id', flat=True)
    )
    watched_tv = set(
        WatchEntry.objects.filter(
            user=request.user,
            media_type=WatchEntryMediaType.EPISODE,
        ).values_list('tmdb_id', flat=True).distinct()
    )
    watchlist_movies = set(
        UserMediaStatus.objects.for_user(request.user).movies().planning().values_list('tmdb_id', flat=True)
    )
    watchlist_tv = set(
        UserMediaStatus.objects.for_user(request.user).shows().planning().values_list('tmdb_id', flat=True)
    )

    excluded_movies = watched_movies | watchlist_movies
    excluded_tv = watched_tv | watchlist_tv

    # Only the "fewer than 3 entries" threshold matters, so never count the whole history.
    insufficient_history = len(WatchEntry.objects.filter(user=request.user).values_list('id', flat=True)[:3]) < 3

    def pick_items(items, excluded, limit=12):
        picked = []
        for item in items:
            tmdb_id = item.get('id')
            if tmdb_id is None or tmdb_id in excluded:
                continue
            picked.append(item)
            if len(picked) >= limit:
                break
        return picked

    movie_results: list[dict[str, Any]] = []
    tv_results: list[dict[str, Any]] = []
    for page in (1, 2):
        if len(movie_results) < 12:
            try:
                movies = tmdb.get_popular_movies(page).get('results', [])
                movie_results.extend(pick_items(movies, excluded_movies, limit=12 - len(movie_results)))
            except Exception as exc:
                logger.warning('Failed fetching popular movies page %s: %s', page, exc)
        if len(tv_results) < 12:
            try:
                shows = tmdb.get_popular_tv(page).get('results', [])
                tv_results.extend(pick_items(shows, excluded_tv, limit=12 - len(tv_results)))
            except Exception as exc:
                logger.warning('Failed fetching popular TV page %s: %s', page, exc)

    return Response({
        'movies': movie_results,
        'tv': tv_results,
        'insufficient_history': insufficient_history,
    })

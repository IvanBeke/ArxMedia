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


def _watched_movie_ids(user) -> set[int]:
    return set(
        WatchEntry.objects.filter(
            user=user,
            media_type=WatchEntryMediaType.MOVIE,
        ).values_list('tmdb_id', flat=True)
    )


def _watched_tv_ids(user) -> set[int]:
    return set(
        WatchEntry.objects.filter(
            user=user,
            media_type=WatchEntryMediaType.EPISODE,
        ).values_list('tmdb_id', flat=True).distinct()
    )


def _planned_movie_ids(user) -> set[int]:
    return set(UserMediaStatus.objects.for_user(user).movies().planning().values_list('tmdb_id', flat=True))


def _planned_tv_ids(user) -> set[int]:
    return set(UserMediaStatus.objects.for_user(user).shows().planning().values_list('tmdb_id', flat=True))


def _pick_popular_items(items, excluded: set[int], limit: int = 12) -> list:
    picked = []
    for item in items:
        tmdb_id = item.get('id')
        if tmdb_id is None or tmdb_id in excluded:
            continue
        picked.append(item)
        if len(picked) >= limit:
            break
    return picked


def _fetch_popular_page(fetch, page: int, excluded: set[int], already_picked: int, label: str) -> list:
    try:
        results = fetch(page).get('results', [])
        return _pick_popular_items(results, excluded, limit=12 - already_picked)
    except Exception as exc:
        logger.warning('Failed fetching %s page %s: %s', label, page, exc)
        return []


def _popular_tmdb_results(fetch, excluded: set[int], label: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for page in (1, 2):
        if len(results) < 12:
            results.extend(_fetch_popular_page(fetch, page, excluded, len(results), label))
    return results


# Calls TMDB and only reads tracking data, so it does not need the request-wide transaction.
@transaction.non_atomic_requests
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def recommendations(request):
    excluded_movies = _watched_movie_ids(request.user) | _planned_movie_ids(request.user)
    excluded_tv = _watched_tv_ids(request.user) | _planned_tv_ids(request.user)

    # Only the "fewer than 3 entries" threshold matters, so never count the whole history.
    insufficient_history = len(WatchEntry.objects.filter(user=request.user).values_list('id', flat=True)[:3]) < 3

    return Response({
        'movies': _popular_tmdb_results(tmdb.get_popular_movies, excluded_movies, 'popular movies'),
        'tv': _popular_tmdb_results(tmdb.get_popular_tv, excluded_tv, 'popular TV'),
        'insufficient_history': insufficient_history,
    })

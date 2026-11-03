from functools import wraps

from django.db import transaction
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .clients import IntegrationError, radarr_client, radarr_public_url
from .permissions import CanUseSonarrRadarr
from .serializers import RadarrAddSerializer, RadarrRemoveSerializer

ARR_PERMISSIONS = [permissions.IsAuthenticated, CanUseSonarrRadarr]


def integration_view(view):
    """Turn external service failures into JSON error responses."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except IntegrationError as exc:
            return Response({'detail': exc.detail}, status=exc.status_code)

    return wrapper


def _movie_state(movie):
    if not movie:
        return {'added': False}
    slug = movie.get('titleSlug') or movie.get('tmdbId')
    return {
        'added': True,
        'path': movie.get('path', ''),
        'monitored': bool(movie.get('monitored')),
        'url': f'{radarr_public_url()}/movie/{slug}',
    }


@transaction.non_atomic_requests
@api_view(['GET'])
@permission_classes(ARR_PERMISSIONS)
@integration_view
def radarr_options(request):
    return Response(radarr_client().options())


def _remove_movie(client, existing, data):
    if not existing:
        return Response({'detail': 'Movie is not in Radarr.'}, status=status.HTTP_404_NOT_FOUND)
    serializer = RadarrRemoveSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    client.remove_movie(existing['id'], serializer.validated_data)
    return Response(_movie_state(None))


@transaction.non_atomic_requests
@api_view(['GET', 'POST', 'DELETE'])
@permission_classes(ARR_PERMISSIONS)
@integration_view
def radarr_movie(request, tmdb_id):
    client = radarr_client()
    existing = client.find_movie(tmdb_id)
    if request.method == 'GET':
        return Response(_movie_state(existing))
    if request.method == 'DELETE':
        return _remove_movie(client, existing, request.data)
    if existing:
        return Response({'detail': 'Movie is already in Radarr.', **_movie_state(existing)}, status=status.HTTP_409_CONFLICT)
    serializer = RadarrAddSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    added = client.add_movie(tmdb_id, serializer.validated_data)
    return Response(_movie_state(added), status=status.HTTP_201_CREATED)

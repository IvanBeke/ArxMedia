from functools import wraps

from django.db import transaction
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .clients import IntegrationError, radarr_client, sonarr_client
from .media_ids import tvdb_id_for_show
from .permissions import CanUseSonarrRadarr
from .serializers import ArrRemoveSerializer, RadarrAddSerializer, SonarrAddSerializer

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


@transaction.non_atomic_requests
@api_view(['GET'])
@permission_classes(ARR_PERMISSIONS)
@integration_view
def radarr_options(request):
    return Response(radarr_client().options())


def _remove_movie(client, existing, data):
    if not existing:
        return Response({'detail': 'Movie is not in Radarr.'}, status=status.HTTP_404_NOT_FOUND)
    serializer = ArrRemoveSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    client.remove_movie(existing['id'], serializer.validated_data)
    return Response(client.movie_state(None))


@transaction.non_atomic_requests
@api_view(['GET', 'POST', 'DELETE'])
@permission_classes(ARR_PERMISSIONS)
@integration_view
def radarr_movie(request, tmdb_id):
    client = radarr_client()
    existing = client.find_movie(tmdb_id)
    if request.method == 'GET':
        return Response(client.movie_state(existing))
    if request.method == 'DELETE':
        return _remove_movie(client, existing, request.data)
    if existing:
        return Response({'detail': 'Movie is already in Radarr.', **client.movie_state(existing)}, status=status.HTTP_409_CONFLICT)
    serializer = RadarrAddSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    added = client.add_movie(tmdb_id, serializer.validated_data)
    return Response(client.movie_state(added), status=status.HTTP_201_CREATED)


@transaction.non_atomic_requests
@api_view(['GET'])
@permission_classes(ARR_PERMISSIONS)
@integration_view
def sonarr_options(request):
    return Response(sonarr_client().options())


def _remove_series(client, existing, data):
    if not existing:
        return Response({'detail': 'Series is not in Sonarr.'}, status=status.HTTP_404_NOT_FOUND)
    serializer = ArrRemoveSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    client.remove_series(existing['id'], serializer.validated_data)
    return Response(client.series_state(None))


@transaction.non_atomic_requests
@api_view(['GET', 'POST', 'DELETE'])
@permission_classes(ARR_PERMISSIONS)
@integration_view
def sonarr_series(request, tmdb_id):
    client = sonarr_client()
    tvdb_id = tvdb_id_for_show(tmdb_id)
    existing = client.find_series(tvdb_id)
    if request.method == 'GET':
        return Response(client.series_state(existing))
    if request.method == 'DELETE':
        return _remove_series(client, existing, request.data)
    if existing:
        return Response({'detail': 'Series is already in Sonarr.', **client.series_state(existing)}, status=status.HTTP_409_CONFLICT)
    serializer = SonarrAddSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    added = client.add_series(tvdb_id, serializer.validated_data)
    return Response(client.series_state(added), status=status.HTTP_201_CREATED)

import logging

from django.db.models import (
    DateTimeField,
    Q,
)
from django.db.models.functions import Coalesce
from django.utils import timezone
from media.tmdb import tmdb
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from ..choices import (
    MediaType,
    TvShowStatus,
    WatchEntryMediaType,
)
from ..models import (
    UserMediaStatus,
    WatchEntry,
)
from ..serializers import WatchlistSerializer
from ..status_annotations import annotate_media_user_status
from ._helpers import (
    _apply_missing_rating_filter,
    _apply_secondary_title_ordering,
    _coerce_int,
    _compute_mixed_runtime_and_counts,
    _normalize_sort,
    _parse_bool_param,
    _parse_multi_param,
)

logger = logging.getLogger(__name__)


class WatchlistListCreateView(generics.ListCreateAPIView):
    serializer_class = WatchlistSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = UserMediaStatus.objects.for_user(self.request.user).planning().annotate(
            added_at=Coalesce('status_changed_at', 'created_at', output_field=DateTimeField())
        )
        media_type = (self.request.query_params.get('media_type') or '').strip().lower()
        if media_type in (MediaType.MOVIE, MediaType.TV):
            qs = qs.filter(media_type=media_type)

        tmdb_id = self.request.query_params.get('tmdb_id')
        if tmdb_id is not None:
            qs = qs.filter(tmdb_id=_coerce_int(tmdb_id, 'tmdb_id'))

        search = (self.request.query_params.get('search') or '').strip()
        if search:
            from media.models import Movie, TVShow
            movie_ids = Movie.objects.filter(title__icontains=search).values_list('tmdb_id', flat=True)
            tv_ids = TVShow.objects.filter(name__icontains=search).values_list('tmdb_id', flat=True)
            qs = qs.filter(
                Q(media_type=MediaType.MOVIE, tmdb_id__in=movie_ids)
                | Q(media_type=MediaType.TV, tmdb_id__in=tv_ids)
            ).distinct()

        selected_genres = _parse_multi_param(self.request.query_params, 'genres')
        if selected_genres:
            from media.models import Movie, TVShow
            movie_ids = Movie.objects.filter(genres__name__in=selected_genres).values_list('tmdb_id', flat=True)
            tv_ids = TVShow.objects.filter(genres__name__in=selected_genres).values_list('tmdb_id', flat=True)
            qs = qs.filter(
                Q(media_type=MediaType.MOVIE, tmdb_id__in=movie_ids)
                | Q(media_type=MediaType.TV, tmdb_id__in=tv_ids)
            ).distinct()

        missing_rating = _parse_bool_param(self.request.query_params.get('missing_rating'))
        if missing_rating is True:
            qs = _apply_missing_rating_filter(qs, self.request.user)

        sort_key, direction = _normalize_sort(
            self.request.query_params.get('sort'),
            self.request.query_params.get('direction'),
            default_sort='added_at',
            default_direction='asc',
        )
        valid_sorts = {
            'added_at', 'title', 'release_date',
            'provider_rating', 'user_rating', 'runtime', 'total_episodes', 'vote_count',
            'watched_date', 'started_date', 'last_watched', 'progress_percent', 'episodes_left', 'time_left', 'next_episode_date'
        }
        if sort_key not in valid_sorts:
            sort_key = 'added_at'

        return _apply_secondary_title_ordering(qs, sort_key, direction, user=self.request.user)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        items = page if page is not None else queryset

        from media.models import Movie, TVShow
        movie_ids = [entry.tmdb_id for entry in items if entry.media_type == MediaType.MOVIE]
        tv_ids = [entry.tmdb_id for entry in items if entry.media_type == MediaType.TV]
        movie_map = {m.tmdb_id: m for m in Movie.objects.filter(tmdb_id__in=movie_ids)}
        tv_map = {s.tmdb_id: s for s in TVShow.objects.filter(tmdb_id__in=tv_ids)}
        status_map = annotate_media_user_status(
            request.user,
            [{'media_type': entry.media_type, 'tmdb_id': entry.tmdb_id} for entry in items],
        )

        context = self.get_serializer_context()
        context.update({'movie_map': movie_map, 'tv_map': tv_map, 'status_map': status_map})
        serializer = self.get_serializer(items, many=True, context=context)
        total_runtime_minutes, counts = _compute_mixed_runtime_and_counts(queryset)

        if page is not None:
            response = self.get_paginated_response(serializer.data)
            response.data['total_runtime_minutes'] = total_runtime_minutes
            response.data['counts'] = counts
            return response

        return Response({
            'results': serializer.data,
            'count': queryset.count(),
            'next': None,
            'previous': None,
            'total_runtime_minutes': total_runtime_minutes,
            'counts': counts,
        })

    def perform_create(self, serializer):
        media_type = serializer.validated_data['media_type']
        tmdb_id = serializer.validated_data['tmdb_id']

        # Check if already watched
        if media_type == MediaType.MOVIE:
            watched = WatchEntry.objects.filter(
                user=self.request.user,
                media_type=WatchEntryMediaType.MOVIE,
                tmdb_id=tmdb_id,
            ).exists()
        else:
            # For TV shows, check if any episodes watched
            watched = UserMediaStatus.objects.for_user(self.request.user).shows().progressable().filter(
                tmdb_id=tmdb_id,
            ).exists()

        if watched:
            raise ValidationError('This content has already been watched and cannot be added to watchlist.')

        try:
            if media_type == MediaType.MOVIE:
                tmdb.sync_movie(tmdb_id)
            elif media_type == MediaType.TV:
                tmdb.sync_tv_show(tmdb_id)
        except Exception as exc:
            logger.warning('Failed to sync %s metadata for watchlist tmdb_id=%s: %s', media_type, tmdb_id, exc)

        instance = UserMediaStatus.objects.set_planning(self.request.user, media_type, tmdb_id)
        serializer.instance = instance


class WatchlistDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = WatchlistSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserMediaStatus.objects.for_user(self.request.user).planning().annotate(
            added_at=Coalesce('status_changed_at', 'created_at', output_field=DateTimeField())
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def drop_media(request):
    """Drop a movie or show while preserving watched history."""
    tmdb_id = request.data.get('tmdb_id')
    media_type = request.data.get('media_type')

    if not tmdb_id:
        return Response({'detail': 'tmdb_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
    if not media_type:
        return Response({'detail': 'media_type is required.'}, status=status.HTTP_400_BAD_REQUEST)
    if media_type not in (MediaType.MOVIE, MediaType.TV):
        return Response({'detail': 'media_type must be one of: movie, tv.'}, status=status.HTTP_400_BAD_REQUEST)

    tmdb_id = _coerce_int(tmdb_id, 'tmdb_id')
    dropped_at = timezone.now()
    UserMediaStatus.objects.update_or_create(
        user=request.user,
        media_type=media_type,
        tmdb_id=tmdb_id,
        defaults={
            'status': TvShowStatus.DROPPED,
            'dropped_at': dropped_at,
            'status_changed_at': dropped_at,
        },
    )

    return Response({'dropped': True})

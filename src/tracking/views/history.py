from django.db import IntegrityError, transaction
from django.db.models import (
    Avg,
    Count,
    F,
    Q,
)
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from accounts.authentication import authenticated_user
from accounts.privacy import visible_owner_q

from ..choices import (
    MediaType,
    TvShowStatus,
    WatchEntryMediaType,
)
from ..models import (
    Rating,
    Review,
    UserMediaStatus,
    WatchEntry,
)
from ..query_helpers import watch_entry_context
from ..serializers import (
    RatingSerializer,
    ReviewSerializer,
    WatchEntrySerializer,
)
from ..watched_at import resolve_watched_at, wants_release_date
from ._helpers import (
    _coerce_int,
)


class WatchEntryListCreateView(generics.ListCreateAPIView):
    serializer_class = WatchEntrySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = WatchEntry.objects.filter(user=authenticated_user(self.request))
        media_type = self.request.query_params.get('media_type')
        if media_type in (WatchEntryMediaType.MOVIE, WatchEntryMediaType.EPISODE):
            qs = qs.filter(media_type=media_type)

        tmdb_id = self.request.query_params.get('tmdb_id')
        if tmdb_id is not None:
            qs = qs.filter(tmdb_id=_coerce_int(tmdb_id, 'tmdb_id'))

        season_number = self.request.query_params.get('season_number')
        if season_number is not None:
            qs = qs.filter(season_number=_coerce_int(season_number, 'season_number'))

        episode_number = self.request.query_params.get('episode_number')
        if episode_number is not None:
            qs = qs.filter(episode_number=_coerce_int(episode_number, 'episode_number'))


        order = (self.request.query_params.get('order') or 'newest').lower()
        if order == 'oldest':
            # Unknown watch dates (null) sort as the oldest entries in both directions.
            return qs.order_by(F('watched_at').asc(nulls_first=True), 'id')
        return qs.order_by(F('watched_at').desc(nulls_last=True), '-id')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        items = page if page is not None else queryset

        movie_ids = [entry.tmdb_id for entry in items if entry.media_type == WatchEntryMediaType.MOVIE]
        show_ids = [entry.tmdb_id for entry in items if entry.media_type == WatchEntryMediaType.EPISODE]
        rating_rows = Rating.objects.filter(
            user=request.user,
        ).filter(
            Q(media_type=MediaType.MOVIE, tmdb_id__in=movie_ids)
            | Q(media_type=MediaType.TV, tmdb_id__in=show_ids)
        ).values('media_type', 'tmdb_id', 'score')
        rating_map = {(row['media_type'], row['tmdb_id']): row['score'] for row in rating_rows}

        context = dict(self.get_serializer_context())
        context.update(watch_entry_context(items))
        serializer = self.get_serializer(items, many=True, context=context)
        data = serializer.data

        for row in data:
            if row['media_type'] == WatchEntryMediaType.MOVIE:
                row['rating'] = rating_map.get((MediaType.MOVIE, row['tmdb_id']))
            elif row['media_type'] == WatchEntryMediaType.EPISODE:
                row['rating'] = rating_map.get((MediaType.TV, row['tmdb_id']))
            else:
                row['rating'] = None

        if page is not None:
            return self.get_paginated_response(data)
        return Response(data)

    def create(self, request, *args, **kwargs):
        # A movie or episode is watched at most once; re-posting it returns the existing entry.
        data = request.data.dict() if hasattr(request.data, 'dict') else dict(request.data)
        data['watched_at'] = resolve_watched_at(data.get('watched_at'), self._release_for(data))
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                self.perform_create(serializer)
        except IntegrityError:
            existing = self._existing_entry(serializer.validated_data)
            if existing is None:
                raise
            return Response(self.get_serializer(existing).data, status=status.HTTP_200_OK)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @staticmethod
    def _release_for(data):
        """Release moment of the posted item, looked up only when the client asked for it."""
        if not wants_release_date(data.get('watched_at')):
            return None
        from media.models import Episode, Movie

        try:
            tmdb_id = int(data.get('tmdb_id'))
        except (TypeError, ValueError):
            return None
        if data.get('media_type') == WatchEntryMediaType.MOVIE:
            return Movie.objects.filter(tmdb_id=tmdb_id).values_list('release_date', flat=True).first()
        row = Episode.objects.filter(
            season__show__tmdb_id=tmdb_id,
            season__season_number=data.get('season_number'),
            episode_number=data.get('episode_number'),
        ).values('broadcast_start', 'air_date').first()
        if row is None:
            return None
        return row.get('broadcast_start') or row.get('air_date')

    def _existing_entry(self, data):
        lookup = {'user': self.request.user, 'media_type': data['media_type'], 'tmdb_id': data['tmdb_id']}
        if data['media_type'] == WatchEntryMediaType.EPISODE:
            lookup |= {'season_number': data.get('season_number'), 'episode_number': data.get('episode_number')}
        return WatchEntry.objects.filter(**lookup).first()

    def perform_create(self, serializer):
        # create() already resolved watched_at; None means the watch date is unknown.
        serializer.save(user=self.request.user)


class WatchEntryDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = WatchEntrySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WatchEntry.objects.filter(user=authenticated_user(self.request))


class RatingListCreateView(generics.ListCreateAPIView):
    serializer_class = RatingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Rating.objects.filter(user=authenticated_user(self.request))
        media_type = self.request.query_params.get('media_type')
        if media_type in (MediaType.MOVIE, MediaType.TV):
            qs = qs.filter(media_type=media_type)
        tmdb_id = self.request.query_params.get('tmdb_id')
        if tmdb_id is not None:
            qs = qs.filter(tmdb_id=_coerce_int(tmdb_id, 'tmdb_id'))
        return qs.order_by('-updated_at')

    def perform_create(self, serializer):
        user = authenticated_user(self.request)
        media_type = serializer.validated_data['media_type']
        tmdb_id = serializer.validated_data['tmdb_id']

        if media_type == MediaType.MOVIE:
            can_rate = WatchEntry.objects.filter(
                user=user,
                media_type=WatchEntryMediaType.MOVIE,
                tmdb_id=tmdb_id,
            ).exists()
        else:
            can_rate = UserMediaStatus.objects.shows().filter(
                user=user,
                tmdb_id=tmdb_id,
                status__in=(TvShowStatus.WATCHING, TvShowStatus.WATCHED, TvShowStatus.DROPPED),
            ).exists()

        if not can_rate:
            if media_type == MediaType.MOVIE:
                raise ValidationError({'detail': 'Rate this movie after marking it as watched.'})
            raise ValidationError({'detail': 'Rate this show after you start watching it.'})

        # Upsert rating
        existing = Rating.objects.filter(
            user=user,
            media_type=media_type,
            tmdb_id=tmdb_id,
        ).first()
        if existing:
            existing.score = serializer.validated_data['score']
            existing.save()
        else:
            serializer.save(user=user)


class ReviewListCreateView(generics.ListCreateAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        media_type = self.request.query_params.get('media_type')
        tmdb_id = self.request.query_params.get('tmdb_id')
        qs = Review.objects.filter(visible_owner_q(self.request.user)).select_related('user')
        if media_type:
            if media_type not in MediaType.values:
                raise ValidationError({'media_type': f'Must be one of: {", ".join(MediaType.values)}.'})
            qs = qs.filter(media_type=media_type)
        if tmdb_id:
            qs = qs.filter(tmdb_id=_coerce_int(tmdb_id, 'tmdb_id'))
        return qs.order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_stats(request):
    from ..cache import cache
    user = request.user
    stats = cache.get_user_stats(user.id)
    entries = WatchEntry.objects.filter(user=user)

    movie_ids = list(entries.filter(media_type=WatchEntryMediaType.MOVIE).values_list('tmdb_id', flat=True))
    top_genres = []
    if movie_ids:
        from media.models import Genre
        genre_counts = Genre.objects.filter(
            movie__tmdb_id__in=movie_ids
        ).annotate(count=Count('id')).order_by('-count')[:5]
        top_genres = [{'name': g.name, 'count': g.count} for g in genre_counts]

    avg_rating = Rating.objects.filter(user=user).aggregate(avg=Avg('score'))['avg']

    recent = list(entries.order_by(F('watched_at').desc(nulls_last=True), '-id')[:10])
    context = watch_entry_context(recent)

    recent_movie_ids = set()
    recent_tv_ids = set()
    for entry in recent:
        if entry.media_type == WatchEntryMediaType.MOVIE:
            recent_movie_ids.add(entry.tmdb_id)
        elif entry.media_type == WatchEntryMediaType.EPISODE:
            recent_tv_ids.add(entry.tmdb_id)

    ratings_qs = Rating.objects.filter(user=user).filter(
        Q(media_type=MediaType.MOVIE, tmdb_id__in=recent_movie_ids)
        | Q(media_type=MediaType.TV, tmdb_id__in=recent_tv_ids)
    ).values('media_type', 'tmdb_id', 'score')
    rating_map = {(row['media_type'], row['tmdb_id']): row['score'] for row in ratings_qs}

    recent_data = []
    for entry in recent:
        d = WatchEntrySerializer(entry, context=context).data
        if entry.media_type == WatchEntryMediaType.MOVIE:
            movie = context['movie_map'].get(entry.tmdb_id)
            d['title'] = movie.title if movie else f'Movie #{entry.tmdb_id}'
            d['poster_path'] = movie.poster_path if movie else ''
            d['show_title'] = None
            d['episode_title'] = None
            d['rating'] = rating_map.get((MediaType.MOVIE, entry.tmdb_id))
        elif entry.media_type == WatchEntryMediaType.EPISODE:
            season = context['season_map'].get((entry.tmdb_id, entry.season_number))
            if season:
                ep = context['episode_map'].get((entry.tmdb_id, entry.season_number, entry.episode_number))
                d['show_title'] = season.show.name
                d['episode_title'] = ep.name if ep else f'Episode {entry.episode_number}'
                d['title'] = d['episode_title']
            else:
                d['show_title'] = None
                d['episode_title'] = f'Episode {entry.episode_number}' if entry.episode_number is not None else f'Episode #{entry.tmdb_id}'
                d['title'] = d['episode_title']
            d['rating'] = rating_map.get((MediaType.TV, entry.tmdb_id))
        recent_data.append(d)

    return Response({
        'movies_watched': stats['movies'],
        'shows_watching': stats['shows_watching'],
        'shows_completed': stats['shows_completed'],
        'episodes_watched': WatchEntry.objects.filter(user=user, media_type=WatchEntryMediaType.EPISODE).count(),
        'average_rating': round(avg_rating, 1) if avg_rating else None,
        'top_genres': top_genres,
        'recent_activity': recent_data,
    })

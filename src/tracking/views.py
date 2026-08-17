import logging
from datetime import timedelta

from accounts.privacy import can_view_account_content, get_viewer_relationship
from django.db.models import Avg, Count, DateTimeField, F, Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from media.tmdb import tmdb
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from .choices import (
    DataImportMode,
    DataTransferFormat,
    DataTransferJobType,
    DataTransferStatus,
    ListPrivacy,
    MediaType,
    TvShowStatus,
    WatchEntryMediaType,
    WatchEntryStatus,
)
from .models import (
    CustomList,
    DataTransferJob,
    ListCollaborator,
    ListItem,
    Rating,
    Review,
    UserTvShowStatus,
    WatchEntry,
    Watchlist,
)
from .serializers import (
    CustomListSerializer,
    DataTransferJobSerializer,
    ListCollaboratorSerializer,
    ListItemSerializer,
    RatingSerializer,
    ReviewSerializer,
    WatchEntrySerializer,
    WatchlistSerializer,
)
from .status_annotations import annotate_media_user_status
from .status_sync import refresh_season_status, refresh_show_status

logger = logging.getLogger(__name__)


def _coerce_int(value, field_name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError({field_name: f'{field_name} must be an integer.'})


def _parse_watched_at(value):
    if not value:
        return None
    try:
        dt = timezone.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _can_view_public_lists(viewer, owner) -> bool:
    relationship = get_viewer_relationship(viewer, owner)
    return can_view_account_content(owner.account_visibility, relationship)


def _can_access_list(viewer, custom_list) -> bool:
    if viewer.is_staff:
        return True
    if custom_list.user_id == viewer.id:
        return True
    if ListCollaborator.objects.filter(custom_list=custom_list, user=viewer).exists():
        return True
    if custom_list.privacy == ListPrivacy.PRIVATE:
        return False
    return _can_view_public_lists(viewer, custom_list.user)


class WatchEntryListCreateView(generics.ListCreateAPIView):
    serializer_class = WatchEntrySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = WatchEntry.objects.filter(user=self.request.user, status=WatchEntryStatus.WATCHED)
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

        qs = qs.annotate(sort_at=Coalesce('watched_at', 'created_at', output_field=DateTimeField()))

        order = (self.request.query_params.get('order') or 'newest').lower()
        if order == 'oldest':
            return qs.order_by(F('sort_at').asc(nulls_last=True), 'id')
        return qs.order_by(F('sort_at').desc(nulls_last=True), '-id')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        items = page if page is not None else queryset

        from media.models import Movie, TVShow
        movie_ids = [entry.tmdb_id for entry in items if entry.media_type == WatchEntryMediaType.MOVIE]
        show_ids = [entry.tmdb_id for entry in items if entry.media_type == WatchEntryMediaType.EPISODE]
        movie_map = {m.tmdb_id: m for m in Movie.objects.filter(tmdb_id__in=movie_ids)}
        tv_map = {s.tmdb_id: s for s in TVShow.objects.filter(tmdb_id__in=show_ids)}

        context = self.get_serializer_context()
        context.update({'movie_map': movie_map, 'tv_map': tv_map})
        serializer = self.get_serializer(items, many=True, context=context)

        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def perform_create(self, serializer):
        watched_at = serializer.validated_data.get('watched_at')
        if not watched_at:
            watched_at = timezone.now()
        instance = serializer.save(user=self.request.user, watched_at=watched_at)
        # Remove from watchlist if marked as watched
        if instance.status == WatchEntryStatus.WATCHED:
            Watchlist.objects.filter(
                user=instance.user,
                media_type=instance.media_type,
                tmdb_id=instance.tmdb_id
            ).delete()


class WatchEntryDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = WatchEntrySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WatchEntry.objects.filter(user=self.request.user)


class RatingListCreateView(generics.ListCreateAPIView):
    serializer_class = RatingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Rating.objects.filter(user=self.request.user)
        media_type = self.request.query_params.get('media_type')
        if media_type in (MediaType.MOVIE, MediaType.TV):
            qs = qs.filter(media_type=media_type)
        tmdb_id = self.request.query_params.get('tmdb_id')
        if tmdb_id is not None:
            qs = qs.filter(tmdb_id=_coerce_int(tmdb_id, 'tmdb_id'))
        return qs.order_by('-updated_at')

    def perform_create(self, serializer):
        media_type = serializer.validated_data['media_type']
        tmdb_id = serializer.validated_data['tmdb_id']

        if media_type == MediaType.MOVIE:
            can_rate = WatchEntry.objects.filter(
                user=self.request.user,
                media_type=WatchEntryMediaType.MOVIE,
                tmdb_id=tmdb_id,
                status=WatchEntryStatus.WATCHED,
            ).exists()
        else:
            can_rate = UserTvShowStatus.objects.filter(
                user=self.request.user,
                tmdb_id=tmdb_id,
                status__in=(TvShowStatus.WATCHING, TvShowStatus.WATCHED, TvShowStatus.DROPPED),
            ).exists()

        if not can_rate:
            if media_type == MediaType.MOVIE:
                raise ValidationError({'detail': 'Rate this movie after marking it as watched.'})
            raise ValidationError({'detail': 'Rate this show after you start watching it.'})

        # Upsert rating
        existing = Rating.objects.filter(
            user=self.request.user,
            media_type=media_type,
            tmdb_id=tmdb_id,
        ).first()
        if existing:
            existing.score = serializer.validated_data['score']
            existing.save()
        else:
            serializer.save(user=self.request.user)


class WatchlistListCreateView(generics.ListCreateAPIView):
    serializer_class = WatchlistSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Watchlist.objects.filter(user=self.request.user)
        media_type = self.request.query_params.get('media_type')
        if media_type:
            qs = qs.filter(media_type=media_type)
        tmdb_id = self.request.query_params.get('tmdb_id')
        if tmdb_id is not None:
            qs = qs.filter(tmdb_id=_coerce_int(tmdb_id, 'tmdb_id'))
        return qs.order_by('-added_at')

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

        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def perform_create(self, serializer):
        media_type = serializer.validated_data['media_type']
        tmdb_id = serializer.validated_data['tmdb_id']

        # Check if already watched
        if media_type == MediaType.MOVIE:
            watched = WatchEntry.objects.filter(
                user=self.request.user,
                media_type=WatchEntryMediaType.MOVIE,
                tmdb_id=tmdb_id,
                status=WatchEntryStatus.WATCHED,
            ).exists()
        else:
            # For TV shows, check if any episodes watched
            watched = WatchEntry.objects.filter(
                user=self.request.user,
                media_type=WatchEntryMediaType.EPISODE,
                tmdb_id=tmdb_id,
                status=WatchEntryStatus.WATCHED,
                season_number__gt=0,
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

        serializer.save(user=self.request.user)


class WatchlistDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = WatchlistSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Watchlist.objects.filter(user=self.request.user)


class ReviewListCreateView(generics.ListCreateAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        media_type = self.request.query_params.get('media_type')
        tmdb_id = self.request.query_params.get('tmdb_id')
        qs = Review.objects.all()
        if media_type:
            qs = qs.filter(media_type=media_type)
        if tmdb_id:
            qs = qs.filter(tmdb_id=tmdb_id)
        return qs.order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_stats(request):
    from .cache import cache
    user = request.user
    stats = cache.get_user_stats(user.id)
    entries = WatchEntry.objects.filter(user=user, status=WatchEntryStatus.WATCHED)

    movie_ids = list(entries.filter(media_type=WatchEntryMediaType.MOVIE).values_list('tmdb_id', flat=True))
    top_genres = []
    if movie_ids:
        from media.models import Genre
        genre_counts = Genre.objects.filter(
            movie__tmdb_id__in=movie_ids
        ).annotate(count=Count('id')).order_by('-count')[:5]
        top_genres = [{'name': g.name, 'count': g.count} for g in genre_counts]

    avg_rating = Rating.objects.filter(user=user).aggregate(avg=Avg('score'))['avg']

    recent = entries.order_by('-watched_at')[:10]
    from media.models import Episode, Movie, Season

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
        d = WatchEntrySerializer(entry).data
        if entry.media_type == WatchEntryMediaType.MOVIE:
            movie = Movie.objects.filter(tmdb_id=entry.tmdb_id).first()
            d['title'] = movie.title if movie else f'Movie #{entry.tmdb_id}'
            d['poster_path'] = movie.poster_path if movie else ''
            d['show_title'] = None
            d['episode_title'] = None
            d['rating'] = rating_map.get((MediaType.MOVIE, entry.tmdb_id))
        elif entry.media_type == WatchEntryMediaType.EPISODE:
            season = Season.objects.filter(show__tmdb_id=entry.tmdb_id, season_number=entry.season_number).first()
            if season:
                ep = Episode.objects.filter(season=season, episode_number=entry.episode_number).first()
                d['show_title'] = season.show.name
                d['episode_title'] = ep.name if ep else f'Episode {entry.episode_number}'
                d['title'] = d['episode_title']
                d['poster_path'] = season.show.poster_path if season.show else ''
            else:
                d['show_title'] = None
                d['episode_title'] = f'Episode {entry.episode_number}' if entry.episode_number else f'Episode #{entry.tmdb_id}'
                d['title'] = d['episode_title']
                d['poster_path'] = ''
            d['rating'] = rating_map.get((MediaType.TV, entry.tmdb_id))
        recent_data.append(d)

    return Response({
        'movies_watched': stats['movies'],
        'shows_watching': stats['shows_watching'],
        'shows_completed': stats['shows_completed'],
        'hours': stats['hours'],
        'episodes_watched': WatchEntry.objects.filter(user=user, media_type=WatchEntryMediaType.EPISODE).count(),
        'average_rating': round(avg_rating, 1) if avg_rating else None,
        'top_genres': top_genres,
        'recent_activity': recent_data,
    })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def mark_episode_watched(request):
    """Mark a single episode as watched."""
    tmdb_id = request.data.get('tmdb_id')
    season_number = request.data.get('season_number')
    episode_number = request.data.get('episode_number')
    watched_at_str = request.data.get('watched_at')

    if not all([tmdb_id, season_number, episode_number]):
        return Response({'detail': 'tmdb_id, season_number, and episode_number are required.'}, status=status.HTTP_400_BAD_REQUEST)

    tmdb_id = _coerce_int(tmdb_id, 'tmdb_id')
    season_number = _coerce_int(season_number, 'season_number')
    episode_number = _coerce_int(episode_number, 'episode_number')

    watched_at = timezone.now()
    if watched_at_str:
        parsed = _parse_watched_at(watched_at_str)
        if parsed is not None:
            watched_at = parsed

    entry, created = WatchEntry.objects.get_or_create(
        user=request.user,
        media_type=WatchEntryMediaType.EPISODE,
        tmdb_id=tmdb_id,
        season_number=season_number,
        episode_number=episode_number,
        defaults={'status': WatchEntryStatus.WATCHED, 'watched_at': watched_at}
    )
    if not created:
        entry.status = WatchEntryStatus.WATCHED
        entry.watched_at = watched_at
        entry.save(update_fields=['status', 'watched_at'])

    from .cache import cache
    cache.mark_episode_watched(request.user.id, tmdb_id, season_number, episode_number)

    return Response({'id': entry.id, 'created': created}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def unmark_episode_watched(request):
    """Unmark a single episode as watched."""
    tmdb_id = request.data.get('tmdb_id')
    season_number = request.data.get('season_number')
    episode_number = request.data.get('episode_number')

    if not all([tmdb_id, season_number, episode_number]):
        return Response({'detail': 'tmdb_id, season_number, and episode_number are required.'}, status=status.HTTP_400_BAD_REQUEST)

    tmdb_id = _coerce_int(tmdb_id, 'tmdb_id')
    season_number = _coerce_int(season_number, 'season_number')
    episode_number = _coerce_int(episode_number, 'episode_number')

    deleted, _ = WatchEntry.objects.filter(
        user=request.user,
        media_type=WatchEntryMediaType.EPISODE,
        tmdb_id=tmdb_id,
        season_number=season_number,
        episode_number=episode_number,
    ).delete()

    if deleted:
        from .cache import cache
        cache.unmark_episode_watched(request.user.id, tmdb_id, season_number, episode_number)

    return Response({'deleted': deleted > 0})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def watched_episodes(request):
    """Get all watched episodes for a specific show."""
    tmdb_id = request.query_params.get('tmdb_id')
    if not tmdb_id:
        return Response({'detail': 'tmdb_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
    tmdb_id = _coerce_int(tmdb_id, 'tmdb_id')

    episodes = WatchEntry.objects.filter(
        user=request.user,
        media_type=WatchEntryMediaType.EPISODE,
        tmdb_id=tmdb_id,
        status=WatchEntryStatus.WATCHED,
    ).values('season_number', 'episode_number', 'watched_at')

    return Response({'episodes': list(episodes)})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def mark_season_watched(request):
    """Mark all episodes in a season as watched."""
    tmdb_id = request.data.get('tmdb_id')
    season_number = request.data.get('season_number')
    watched_at_str = request.data.get('watched_at')
    use_release_date = request.data.get('use_release_date', False)

    if not all([tmdb_id, season_number]):
        return Response({'detail': 'tmdb_id and season_number are required.'}, status=status.HTTP_400_BAD_REQUEST)

    tmdb_id = _coerce_int(tmdb_id, 'tmdb_id')
    season_number = _coerce_int(season_number, 'season_number')

    # Fetch episode numbers and air dates from the Episode model
    from media.models import Episode, Season
    try:
        season = Season.objects.get(show__tmdb_id=tmdb_id, season_number=season_number)
        episodes = list(Episode.objects.filter(season=season).values('episode_number', 'air_date'))
        
        # If no episodes synced yet, sync the season first
        if not episodes:
            from media.tmdb import tmdb
            try:
                tmdb.sync_season(season.show, season_number)
                episodes = list(Episode.objects.filter(season=season).values('episode_number', 'air_date'))
            except Exception as exc:
                logger.warning('Failed to sync season %s for show %s: %s', season_number, tmdb_id, exc)
    except Season.DoesNotExist:
        return Response({'detail': 'Season not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Bulk create all watch entries
    entries = []
    for ep in episodes:
        watched_at = timezone.now()
        if use_release_date and ep['air_date']:
            watched_at = timezone.make_aware(
                timezone.datetime.combine(ep['air_date'], timezone.datetime.min.time()),
                timezone.get_current_timezone(),
            )
        elif watched_at_str:
            parsed = _parse_watched_at(watched_at_str)
            if parsed is not None:
                watched_at = parsed
        
        entries.append(WatchEntry(
            user=request.user,
            media_type=WatchEntryMediaType.EPISODE,
            tmdb_id=tmdb_id,
            season_number=season_number,
            episode_number=ep['episode_number'],
            status=WatchEntryStatus.WATCHED,
            watched_at=watched_at
        ))
    
    WatchEntry.objects.bulk_create(
        entries,
        ignore_conflicts=True
    )

    from .cache import cache
    for ep in episodes:
        cache.mark_episode_watched(request.user.id, tmdb_id, season_number, ep['episode_number'])

    refresh_season_status(request.user.id, tmdb_id, season_number)
    refresh_show_status(request.user.id, tmdb_id)

    return Response({'marked': len(episodes)})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def unmark_season_watched(request):
    """Unmark all episodes in a season."""
    tmdb_id = request.data.get('tmdb_id')
    season_number = request.data.get('season_number')

    if not all([tmdb_id, season_number]):
        return Response({'detail': 'tmdb_id and season_number are required.'}, status=status.HTTP_400_BAD_REQUEST)

    tmdb_id = _coerce_int(tmdb_id, 'tmdb_id')
    season_number = _coerce_int(season_number, 'season_number')

    count, _ = WatchEntry.objects.filter(
        user=request.user,
        media_type=WatchEntryMediaType.EPISODE,
        tmdb_id=tmdb_id,
        season_number=season_number
    ).delete()

    return Response({'unmarked': count})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def up_next(request):
    """Get next episodes for currently watching shows."""
    from django.utils import timezone
    from media.models import Episode, Season, TVShow

    today = timezone.now().date()

    from .models import UserTvShowStatus

    watched_show_ids = UserTvShowStatus.objects.filter(
        user=request.user,
        status__in=(TvShowStatus.WATCHING, TvShowStatus.WATCHED),
        watched_episodes__gt=0,
    ).values('tmdb_id', 'last_watched_at').order_by('-last_watched_at', '-tmdb_id')

    up_next_data = []
    new_threshold = today - timedelta(days=7)
    for show_item in watched_show_ids:
        tmdb_id = show_item['tmdb_id']
        show = TVShow.objects.filter(tmdb_id=tmdb_id).first()
        if not show:
            continue

        watched_eps = set(
            WatchEntry.objects.filter(
                user=request.user,
                media_type=WatchEntryMediaType.EPISODE,
                tmdb_id=tmdb_id,
                season_number__gt=0,
            ).values_list('season_number', 'episode_number')
        )

        seasons = Season.objects.filter(show=show, season_number__gt=0).order_by('season_number')
        found_next = False
        for season in seasons:
            if found_next:
                break
            episodes = Episode.objects.filter(
                season=season,
                air_date__lte=today
            ).order_by('episode_number')
            for episode in episodes:
                if (season.season_number, episode.episode_number) not in watched_eps:
                    up_next_data.append({
                        'tmdb_id': tmdb_id,
                        'show_name': show.name,
                        'poster_path': show.poster_path,
                        'poster_url': show.poster_url,
                        'last_watched_at': show_item['last_watched_at'],
                        'next_episode': {
                            'season_number': episode.season.season_number,
                            'episode_number': episode.episode_number,
                            'name': episode.name,
                            'still_path': episode.still_path,
                            'still_url': episode.still_url,
                            'air_date': episode.air_date,
                        }
                    })
                    found_next = True
                    break

    new_items = []
    old_items = []
    for item in up_next_data:
        air_date = item.get('next_episode', {}).get('air_date')
        is_new = bool(air_date and new_threshold <= air_date <= today)
        item['is_new'] = is_new
        if is_new:
            new_items.append(item)
        else:
            old_items.append(item)

    new_items.sort(key=lambda item: item['next_episode']['air_date'], reverse=True)
    ordered_items = new_items + old_items

    for item in ordered_items:
        item.pop('last_watched_at', None)

    return Response(ordered_items)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def upcoming(request):
    """Get next UPCOMING episode for shows user is watching. Only one per show, max 5."""
    from django.utils import timezone
    from media.models import Episode

    from .models import UserTvShowStatus

    shows_with_episodes = UserTvShowStatus.objects.filter(
        user=request.user,
        status__in=(TvShowStatus.WATCHING, TvShowStatus.WATCHED),
        watched_episodes__gt=0,
    ).values_list('tmdb_id', flat=True).distinct()

    today = timezone.now().date()
    
    # Get all upcoming episodes
    all_upcoming = Episode.objects.filter(
        season__show__tmdb_id__in=shows_with_episodes,
        season__season_number__gt=0,
        air_date__gte=today
    ).order_by('air_date')

    # Group by show and take only the first (next) episode per show
    show_first_ep = {}
    for ep in all_upcoming:
        show_id = ep.season.show.tmdb_id
        if show_id not in show_first_ep:
            show_first_ep[show_id] = ep
            if len(show_first_ep) >= 5:
                break

    upcoming_data = []
    for ep in show_first_ep.values():
        upcoming_data.append({
            'tmdb_id': ep.season.show.tmdb_id,
            'show_name': ep.season.show.name,
            'poster_path': ep.season.show.poster_path,
            'poster_url': ep.season.show.poster_url,
            'season_number': ep.season.season_number,
            'episode_number': ep.episode_number,
            'name': ep.name,
            'still_path': ep.still_path,
            'still_url': ep.still_url,
            'air_date': ep.air_date,
        })

    return Response(upcoming_data)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def drop_show(request):
    """Drop a show while preserving watched episode history."""
    tmdb_id = request.data.get('tmdb_id')

    if not tmdb_id:
        return Response({'detail': 'tmdb_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

    tmdb_id = _coerce_int(tmdb_id, 'tmdb_id')
    dropped_at = timezone.now()
    dropped_entry = WatchEntry.objects.filter(
        user=request.user,
        media_type=WatchEntryMediaType.EPISODE,
        tmdb_id=tmdb_id,
        season_number__isnull=True,
        episode_number__isnull=True,
        status=WatchEntryStatus.DROPPED,
    ).order_by('-id').first()

    if dropped_entry:
        dropped_entry.watched_at = dropped_at
        dropped_entry.save(update_fields=['watched_at'])
    else:
        WatchEntry.objects.create(
            user=request.user,
            media_type=WatchEntryMediaType.EPISODE,
            tmdb_id=tmdb_id,
            season_number=None,
            episode_number=None,
            status=WatchEntryStatus.DROPPED,
            watched_at=dropped_at,
        )

    Watchlist.objects.filter(
        user=request.user,
        media_type=MediaType.TV,
        tmdb_id=tmdb_id,
    ).delete()

    return Response({'dropped': True})


class CustomListListCreateView(generics.ListCreateAPIView):
    serializer_class = CustomListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return CustomList.objects.all()

        visible_public_lists = Q(privacy=ListPrivacy.PUBLIC) & (
            Q(user__account_visibility='public') |
            Q(
                user__account_visibility='friends_only',
                user__followers__follower=self.request.user,
                user__following__following=self.request.user,
            )
        )

        return CustomList.objects.filter(
            Q(user=self.request.user) |
            Q(collaboratorships__user=self.request.user) |
            visible_public_lists
        ).distinct()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class CustomListDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CustomListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CustomList.objects.all()

    def get_object(self):
        obj = super().get_object()
        if not _can_access_list(self.request.user, obj):
            raise PermissionDenied('You do not have permission to access this list.')
        return obj

    def perform_update(self, serializer):
        # Only owner can update
        if serializer.instance.user != self.request.user:
            raise PermissionDenied('You can only edit your own lists.')
        serializer.save()

    def perform_destroy(self, instance):
        # Only owner can delete
        if instance.user != self.request.user:
            raise PermissionDenied('You can only delete your own lists.')
        instance.delete()


class ListItemListCreateView(generics.ListCreateAPIView):
    serializer_class = ListItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        list_id = self.kwargs.get('list_id')
        try:
            custom_list = CustomList.objects.get(id=list_id)
        except CustomList.DoesNotExist:
            raise PermissionDenied('List not found.')

        if not _can_access_list(self.request.user, custom_list):
            raise PermissionDenied('You do not have permission to access this list.')

        queryset = ListItem.objects.filter(custom_list=custom_list).select_related('custom_list')
        
        # Sorting
        sort_by = self.request.query_params.get('sort', '-added_at')
        valid_sorts = ['added_at', '-added_at', 'media_type', '-media_type']
        if sort_by in valid_sorts:
            queryset = queryset.order_by(sort_by)
        else:
            queryset = queryset.order_by('-added_at')
        
        # Search by title
        search = self.request.query_params.get('search')
        if search:
            from media.models import Movie, TVShow
            movie_ids = Movie.objects.filter(title__icontains=search).values_list('tmdb_id', flat=True)
            tv_ids = TVShow.objects.filter(name__icontains=search).values_list('tmdb_id', flat=True)
            queryset = queryset.filter(
                Q(media_type=MediaType.MOVIE, tmdb_id__in=movie_ids) |
                Q(media_type=MediaType.TV, tmdb_id__in=tv_ids)
            ).distinct()
        return queryset

    def perform_create(self, serializer):
        list_id = self.kwargs.get('list_id')
        custom_list = CustomList.objects.get(id=list_id)
        is_owner = custom_list.user_id == self.request.user.id
        is_collaborator = ListCollaborator.objects.filter(custom_list=custom_list, user=self.request.user).exists()
        if not (is_owner or is_collaborator):
            raise PermissionDenied('You can only add items to your lists or lists where you collaborate.')
        serializer.save(custom_list=custom_list)

    def create(self, request, *args, **kwargs):
        # Support bulk create
        if isinstance(request.data, list):
            list_id = self.kwargs.get('list_id')
            custom_list = CustomList.objects.get(id=list_id)
            is_owner = custom_list.user_id == request.user.id
            is_collaborator = ListCollaborator.objects.filter(custom_list=custom_list, user=request.user).exists()
            if not (is_owner or is_collaborator):
                raise PermissionDenied('You can only add items to your lists or lists where you collaborate.')
            items = []
            for item_data in request.data:
                items.append(
                    ListItem(
                        custom_list=custom_list,
                        media_type=item_data.get('media_type'),
                        tmdb_id=item_data.get('tmdb_id')
                    )
                )
            ListItem.objects.bulk_create(items, ignore_conflicts=True)
            return Response({'added': len(items)}, status=status.HTTP_201_CREATED)
        return super().create(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        items = page if page is not None else queryset

        from media.models import Movie, TVShow
        movie_ids = [entry.tmdb_id for entry in items if entry.media_type == MediaType.MOVIE]
        tv_ids = [entry.tmdb_id for entry in items if entry.media_type == MediaType.TV]
        movie_map = {m.tmdb_id: m for m in Movie.objects.filter(tmdb_id__in=movie_ids)}
        tv_map = {s.tmdb_id: s for s in TVShow.objects.filter(tmdb_id__in=tv_ids)}

        context = self.get_serializer_context()
        context.update({'movie_map': movie_map, 'tv_map': tv_map})
        serializer = self.get_serializer(items, many=True, context=context)

        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class ListItemDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = ListItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ListItem.objects.filter(
            Q(custom_list__user=self.request.user) |
            Q(custom_list__collaboratorships__user=self.request.user)
        ).distinct()


class ListCollaboratorCreateView(generics.CreateAPIView):
    serializer_class = ListCollaboratorSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        list_id = self.kwargs.get('list_id')
        custom_list = CustomList.objects.get(id=list_id)
        if custom_list.user_id != request.user.id:
            raise PermissionDenied('Only list owner can add collaborators.')

        user_id = request.data.get('user_id')
        if not user_id:
            raise ValidationError({'user_id': 'user_id is required.'})

        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            collaborator_user = User.objects.get(id=int(user_id))
        except (User.DoesNotExist, ValueError):
            raise ValidationError({'user_id': 'Invalid user_id.'})

        if collaborator_user.id == custom_list.user_id:
            raise ValidationError({'user_id': 'Owner is already the list owner.'})

        collab, _ = ListCollaborator.objects.get_or_create(custom_list=custom_list, user=collaborator_user)
        serializer = self.get_serializer(collab)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ListCollaboratorDeleteView(generics.DestroyAPIView):
    serializer_class = ListCollaboratorSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ListCollaborator.objects.filter(custom_list__user=self.request.user)

    def get_object(self):
        list_id = self.kwargs.get('list_id')
        user_id = self.kwargs.get('user_id')
        return self.get_queryset().get(custom_list_id=list_id, user_id=user_id)


class DataImportView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        fmt = request.query_params.get('data_format', request.query_params.get('format', DataTransferFormat.JSON)).lower()
        if fmt not in (DataTransferFormat.JSON, DataTransferFormat.CSV, DataTransferFormat.ZIP):
            raise ValidationError({'format': 'format must be json, csv, or zip'})
        source = (request.query_params.get('source') or '').strip().lower()
        uploaded = request.FILES.get('file')
        if not uploaded:
            raise ValidationError({'file': 'file is required'})

        source_formats = {
            'arxmedia': DataTransferFormat.JSON,
            'trakt': DataTransferFormat.ZIP,
            'yamtrack': DataTransferFormat.CSV,
        }
        if not source:
            raise ValidationError({'source': 'source is required (arxmedia, trakt, or yamtrack).'})
        if source not in source_formats:
            raise ValidationError({'source': 'source must be arxmedia, trakt, or yamtrack'})
        if fmt != source_formats[source]:
            raise ValidationError({'format': f'format must be {source_formats[source]} for source={source}.'})

        job = DataTransferJob.objects.create(
            user=request.user,
            job_type=DataTransferJobType.IMPORT,
            data_format=fmt,
            status=DataTransferStatus.PENDING,
            input_file=uploaded,
        )

        metadata = dict(job.metadata or {})
        metadata['import_source'] = source
        job.metadata = metadata
        job.save(update_fields=['metadata', 'updated_at'])

        if source == 'trakt':
            from .tasks import prepare_trakt_zip_import
            prepare_trakt_zip_import.delay(job.id)
        elif source == 'yamtrack':
            from .tasks import prepare_yamtrack_csv_import
            prepare_yamtrack_csv_import.delay(job.id)
        else:
            from .tasks import import_user_data
            import_user_data.delay(job.id)
        return Response(DataTransferJobSerializer(job, context={'request': request}).data, status=status.HTTP_201_CREATED)


class DataExportView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        fmt = request.query_params.get('data_format', request.query_params.get('format', DataTransferFormat.JSON)).lower()
        if fmt != DataTransferFormat.JSON:
            raise ValidationError({'format': 'format must be json'})
        job = DataTransferJob.objects.create(
            user=request.user,
            job_type=DataTransferJobType.EXPORT,
            data_format=fmt,
            status=DataTransferStatus.PENDING,
        )
        from .tasks import export_user_data
        export_user_data.delay(job.id)
        return Response(DataTransferJobSerializer(job, context={'request': request}).data, status=status.HTTP_201_CREATED)


class DataJobStatusView(generics.RetrieveAPIView):
    serializer_class = DataTransferJobSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return DataTransferJob.objects.filter(user=self.request.user)


class DataJobListView(generics.ListAPIView):
    serializer_class = DataTransferJobSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return DataTransferJob.objects.filter(user=self.request.user)


class DataJobConfirmView(generics.GenericAPIView):
    serializer_class = DataTransferJobSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        job = DataTransferJob.objects.filter(user=request.user, id=kwargs.get('pk')).first()
        if not job:
            raise ValidationError({'job': 'Import job not found.'})
        import_source = (job.metadata or {}).get('import_source')
        can_confirm_trakt_zip = job.data_format == DataTransferFormat.ZIP and import_source == 'trakt'
        can_confirm_yamtrack_csv = job.data_format == DataTransferFormat.CSV and import_source == 'yamtrack'
        if job.job_type != DataTransferJobType.IMPORT or not (can_confirm_trakt_zip or can_confirm_yamtrack_csv):
            raise ValidationError({'job': 'Only Trakt ZIP or Yamtrack CSV import jobs can be confirmed.'})
        if job.status != DataTransferStatus.AWAITING_CONFIRMATION:
            raise ValidationError({'job': 'Import job is not ready for confirmation.'})

        import_mode = (request.data.get('import_mode') or '').strip().lower()
        if import_mode not in DataImportMode.values:
            raise ValidationError({'import_mode': 'import_mode must be new_items, update_existing, or mirror_imported_set'})

        metadata = dict(job.metadata or {})
        metadata['import_mode'] = import_mode
        job.metadata = metadata
        job.overwrite_existing = import_mode in (DataImportMode.UPDATE_EXISTING, DataImportMode.MIRROR_IMPORTED_SET)
        job.status = DataTransferStatus.PROCESSING
        job.processed_items = 0
        job.error_message = ''
        job.save(update_fields=['metadata', 'overwrite_existing', 'status', 'processed_items', 'error_message', 'updated_at'])

        if can_confirm_trakt_zip:
            from .tasks import apply_trakt_zip_import
            apply_trakt_zip_import.delay(job.id)
        else:
            from .tasks import apply_yamtrack_csv_import
            apply_yamtrack_csv_import.delay(job.id)
        serializer = self.get_serializer(job, context={'request': request})
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def recommendations(request):
    watched_movies = set(
        WatchEntry.objects.filter(
            user=request.user,
            media_type=WatchEntryMediaType.MOVIE,
            status=WatchEntryStatus.WATCHED,
        ).values_list('tmdb_id', flat=True)
    )
    watched_tv = set(
        WatchEntry.objects.filter(
            user=request.user,
            media_type=WatchEntryMediaType.EPISODE,
            status=WatchEntryStatus.WATCHED,
        ).values_list('tmdb_id', flat=True)
    )
    watchlist_movies = set(
        Watchlist.objects.filter(user=request.user, media_type=MediaType.MOVIE).values_list('tmdb_id', flat=True)
    )
    watchlist_tv = set(
        Watchlist.objects.filter(user=request.user, media_type=MediaType.TV).values_list('tmdb_id', flat=True)
    )

    excluded_movies = watched_movies | watchlist_movies
    excluded_tv = watched_tv | watchlist_tv

    history_count = WatchEntry.objects.filter(user=request.user, status=WatchEntryStatus.WATCHED).count()

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

    movie_results = []
    tv_results = []
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
        'insufficient_history': history_count < 3,
    })

import logging
from datetime import date, timedelta

from accounts.privacy import can_view_account_content, get_viewer_relationship
from django.db import IntegrityError
from django.db.models import (
    Avg,
    Case,
    Count,
    DateField,
    DateTimeField,
    Exists,
    ExpressionWrapper,
    F,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce, Greatest, Lower
from django.utils import timezone
from media.tmdb import tmdb
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
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
)
from .import_config import expected_format_for_source, supported_import_sources
from .import_errors import ImportDomainError, ImportErrorCode, raise_import_validation_error
from .models import (
    CustomList,
    DataTransferJob,
    ListCollaborator,
    ListItem,
    Rating,
    Review,
    UserMediaStatus,
    WatchEntry,
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
from .status_sync import refresh_show_status
from .tasks.import_commands import ConfirmImportCommand

logger = logging.getLogger(__name__)


def _raise_import_error(code: str, message: str, field: str = 'job'):
    raise_import_validation_error(ImportDomainError(code=code, message=message, field=field))


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


def _parse_bool_param(value):
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized in ('1', 'true', 'yes', 'on'):
        return True
    if normalized in ('0', 'false', 'no', 'off'):
        return False
    return None


def _parse_multi_param(query_params, key: str) -> list[str]:
    values = []
    for raw in query_params.getlist(key):
        values.extend([part.strip() for part in str(raw).split(',') if part.strip()])
    return values


def _collect_media_ids(queryset) -> tuple[set[int], set[int]]:
    pairs = queryset.values_list('media_type', 'tmdb_id').distinct()
    movie_ids: set[int] = set()
    tv_ids: set[int] = set()
    for media_type, tmdb_id in pairs:
        if media_type == MediaType.MOVIE:
            movie_ids.add(tmdb_id)
        elif media_type == MediaType.TV:
            tv_ids.add(tmdb_id)
    return movie_ids, tv_ids


def _build_user_media_sets(user, movie_ids: set[int], tv_ids: set[int]) -> dict[str, set[int]]:
    movie_watched_ids = set(
        WatchEntry.objects.filter(
            user=user,
            media_type=WatchEntryMediaType.MOVIE,
            tmdb_id__in=movie_ids,
        ).values_list('tmdb_id', flat=True)
    )
    movie_watchlist_ids = set(
        UserMediaStatus.objects.for_user(user).movies().planning().filter(
            tmdb_id__in=movie_ids,
        ).values_list('tmdb_id', flat=True)
    )
    tv_watchlist_ids = set(
        UserMediaStatus.objects.for_user(user).shows().planning().filter(
            tmdb_id__in=tv_ids,
        ).values_list('tmdb_id', flat=True)
    )
    tv_status_rows = UserMediaStatus.objects.for_user(user).shows().filter(
        tmdb_id__in=tv_ids,
    ).exclude(
        status=TvShowStatus.PLAN_TO_WATCH,
    ).values_list('tmdb_id', 'status')

    tv_watching_ids: set[int] = set()
    tv_watched_ids: set[int] = set()
    tv_dropped_ids: set[int] = set()

    for tmdb_id, show_status in tv_status_rows:
        if show_status == TvShowStatus.WATCHING:
            tv_watching_ids.add(tmdb_id)
        elif show_status == TvShowStatus.WATCHED:
            tv_watched_ids.add(tmdb_id)
        elif show_status == TvShowStatus.DROPPED:
            tv_dropped_ids.add(tmdb_id)
    return {
        'movie_watched': movie_watched_ids,
        'movie_plan_to_watch': movie_watchlist_ids,
        'tv_watching': tv_watching_ids,
        'tv_watched': tv_watched_ids,
        'tv_dropped': tv_dropped_ids,
        'tv_plan_to_watch': tv_watchlist_ids,
        'watchlist_movie': movie_watchlist_ids,
        'watchlist_tv': tv_watchlist_ids,
    }


def _apply_status_filter(queryset, user, selected_statuses: list[str]):
    normalized = {value.strip().lower() for value in selected_statuses if value and value.strip()}
    if not normalized:
        return queryset

    movie_ids, tv_ids = _collect_media_ids(queryset)
    if not movie_ids and not tv_ids:
        return queryset

    sets = _build_user_media_sets(user, movie_ids, tv_ids)
    status_q = Q()

    if 'plan_to_watch' in normalized:
        status_q |= Q(media_type=MediaType.MOVIE, tmdb_id__in=sets['movie_plan_to_watch'])
        status_q |= Q(media_type=MediaType.TV, tmdb_id__in=sets['tv_plan_to_watch'])
    if 'watching' in normalized:
        status_q |= Q(media_type=MediaType.TV, tmdb_id__in=sets['tv_watching'])
    if 'watched' in normalized:
        status_q |= Q(media_type=MediaType.MOVIE, tmdb_id__in=sets['movie_watched'])
        status_q |= Q(media_type=MediaType.TV, tmdb_id__in=sets['tv_watched'])
    if 'dropped' in normalized:
        status_q |= Q(media_type=MediaType.TV, tmdb_id__in=sets['tv_dropped'])

    if not status_q:
        return queryset.none()
    return queryset.filter(status_q)


def _apply_missing_rating_filter(queryset, user):
    movie_ids, tv_ids = _collect_media_ids(queryset)
    if not movie_ids and not tv_ids:
        return queryset

    sets = _build_user_media_sets(user, movie_ids, tv_ids)
    rating_rows = Rating.objects.filter(
        user=user,
        media_type__in=(MediaType.MOVIE, MediaType.TV),
        tmdb_id__in=(movie_ids | tv_ids),
    ).values_list('media_type', 'tmdb_id')

    rated_movie_ids = set()
    rated_tv_ids = set()
    for media_type, tmdb_id in rating_rows:
        if media_type == MediaType.MOVIE:
            rated_movie_ids.add(tmdb_id)
        elif media_type == MediaType.TV:
            rated_tv_ids.add(tmdb_id)

    eligible_movie_ids = (movie_ids - sets['movie_plan_to_watch']) - rated_movie_ids
    eligible_tv_ids = (tv_ids - sets['tv_plan_to_watch']) - rated_tv_ids

    return queryset.filter(
        Q(media_type=MediaType.MOVIE, tmdb_id__in=eligible_movie_ids)
        | Q(media_type=MediaType.TV, tmdb_id__in=eligible_tv_ids)
    )


def _apply_in_watchlist_filter(queryset, user):
    movie_ids = UserMediaStatus.objects.for_user(user).movies().planning().values_list('tmdb_id', flat=True)
    tv_ids = UserMediaStatus.objects.for_user(user).shows().planning().values_list('tmdb_id', flat=True)
    return queryset.filter(
        Q(media_type=MediaType.MOVIE, tmdb_id__in=movie_ids)
        | Q(media_type=MediaType.TV, tmdb_id__in=tv_ids)
    )


def _build_tv_runtime_map(tmdb_ids: list[int]) -> dict[int, int]:
    if not tmdb_ids:
        return {}

    from media.models import Episode

    rows = Episode.objects.filter(
        season__show__tmdb_id__in=tmdb_ids
    ).values('season__show__tmdb_id').annotate(
        total_runtime=Sum('runtime')
    )

    return {
        row['season__show__tmdb_id']: row['total_runtime']
        for row in rows
        if row['total_runtime'] is not None
    }


def _normalize_sort(sort_raw: str | None, direction_raw: str | None, default_sort: str, default_direction: str) -> tuple[str, str]:
    sort_value = (sort_raw or default_sort).strip().lower()
    direction = (direction_raw or '').strip().lower()

    if sort_value.startswith('-'):
        sort_value = sort_value[1:]
        direction = 'desc'

    if direction not in ('asc', 'desc'):
        direction = default_direction

    return sort_value, direction


def _annotate_media_sort_fields(queryset, user=None):
    from media.models import Episode, Movie, TVShow

    movie_lookup = Movie.objects.filter(tmdb_id=OuterRef('tmdb_id'))
    tv_lookup = TVShow.objects.filter(tmdb_id=OuterRef('tmdb_id'))

    tv_status_lookup = UserMediaStatus.objects.none()
    movie_watch_lookup = WatchEntry.objects.none()
    if user and user.is_authenticated:
        tv_status_lookup = UserMediaStatus.objects.shows().filter(user=user, tmdb_id=OuterRef('tmdb_id'))
        movie_watch_lookup = WatchEntry.objects.filter(
            user=user,
            media_type=WatchEntryMediaType.MOVIE,
            tmdb_id=OuterRef('tmdb_id'),
        ).annotate(event_at=Coalesce('watched_at', 'created_at', output_field=DateTimeField())).order_by('-event_at', '-id')

    today = timezone.now().date()

    annotated = queryset.annotate(
        movie_title=Subquery(movie_lookup.values('title')[:1]),
        tv_title=Subquery(tv_lookup.values('name')[:1]),
        movie_release_date=Subquery(movie_lookup.values('release_date')[:1]),
        tv_first_air_date=Subquery(tv_lookup.values('first_air_date')[:1]),
        movie_runtime=Subquery(movie_lookup.values('runtime')[:1]),
        tv_total_runtime=Subquery(
            Episode.objects.filter(
                season__show__tmdb_id=OuterRef('tmdb_id')
            ).values('season__show__tmdb_id').annotate(
                total_runtime=Sum('runtime')
            ).values('total_runtime')[:1]
        ),
        movie_total_episodes=Value(None, output_field=IntegerField()),
        tv_total_episodes=Subquery(tv_lookup.values('number_of_episodes')[:1]),
        movie_vote_average=Subquery(movie_lookup.values('vote_average')[:1]),
        tv_vote_average=Subquery(tv_lookup.values('vote_average')[:1]),
        movie_vote_count=Subquery(movie_lookup.values('vote_count')[:1]),
        tv_vote_count=Subquery(tv_lookup.values('vote_count')[:1]),
        tv_episode_runtime=Subquery(tv_lookup.values('episode_runtime')[:1]),
        tv_started_at=Subquery(tv_status_lookup.values('started_at')[:1]),
        tv_last_watched_at=Subquery(tv_status_lookup.values('last_watched_at')[:1]),
        tv_progress_percent=Subquery(tv_status_lookup.values('progress_percent')[:1]),
        tv_watched_episodes=Subquery(tv_status_lookup.values('watched_episodes')[:1]),
        tv_next_episode_date=Subquery(
            Episode.objects.filter(
                season__show__tmdb_id=OuterRef('tmdb_id'),
                season__season_number__gt=0,
                air_date__gte=today,
            ).order_by('air_date', 'season__season_number', 'episode_number').values('air_date')[:1]
        ),
        movie_watched_date=Subquery(movie_watch_lookup.values('event_at')[:1]),
    ).annotate(
        resolved_title=Lower(Coalesce('movie_title', 'tv_title', Value(''))),
        resolved_date=Coalesce('movie_release_date', 'tv_first_air_date'),
        resolved_runtime=Coalesce('movie_runtime', 'tv_total_runtime'),
        resolved_total_episodes=Coalesce('movie_total_episodes', 'tv_total_episodes'),
        resolved_vote_average=Coalesce('movie_vote_average', 'tv_vote_average', Value(0.0)),
        resolved_vote_count=Coalesce('movie_vote_count', 'tv_vote_count', Value(0)),
        resolved_watched_date=Coalesce('movie_watched_date', 'tv_last_watched_at'),
        resolved_started_date=Coalesce('movie_watched_date', 'tv_started_at'),
        resolved_progress_percent=Coalesce(
            'tv_progress_percent',
            Case(
                When(movie_watched_date__isnull=False, then=Value(100)),
                default=Value(0),
                output_field=IntegerField(),
            )
        ),
        resolved_episodes_left=Greatest(
            Value(0),
            Coalesce('tv_total_episodes', Value(0)) - Coalesce('tv_watched_episodes', Value(0)),
            output_field=IntegerField(),
        ),
        resolved_next_episode_date=Coalesce('tv_next_episode_date', Value(None, output_field=DateField())),
    )

    return annotated.annotate(
        resolved_time_left=ExpressionWrapper(
            Coalesce(F('resolved_episodes_left'), Value(0)) * Coalesce(F('tv_episode_runtime'), Value(0)),
            output_field=IntegerField(),
        ),
    )


def _apply_secondary_title_ordering(queryset, sort_key: str, direction: str, id_desc: bool = False, user=None):
    queryset = _annotate_media_sort_fields(queryset, user=user)

    id_order = '-id' if id_desc else 'id'

    if sort_key == 'title':
        if direction == 'desc':
            return queryset.order_by('-resolved_title', id_order)
        return queryset.order_by('resolved_title', id_order)

    if sort_key == 'media_type':
        if direction == 'desc':
            return queryset.order_by('-media_type', 'resolved_title', id_order)
        return queryset.order_by('media_type', 'resolved_title', id_order)

    if sort_key in ('release_date', 'next_episode_date', 'watched_date', 'started_date', 'last_watched'):
        date_field = 'resolved_date'
        if sort_key == 'next_episode_date':
            date_field = 'resolved_next_episode_date'
        elif sort_key in ('watched_date', 'last_watched'):
            date_field = 'resolved_watched_date'
        elif sort_key == 'started_date':
            date_field = 'resolved_started_date'
        if direction == 'desc':
            return queryset.order_by(F(date_field).desc(nulls_last=True), 'resolved_title', id_order)

        if sort_key == 'next_episode_date':
            return queryset.order_by(
                Case(
                    When(resolved_next_episode_date__isnull=True, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                ),
                F(date_field).asc(nulls_last=True),
                'resolved_title',
                id_order,
            )
        return queryset.order_by(F(date_field).asc(nulls_last=True), 'resolved_title', id_order)

    field_by_sort = {
        'runtime': 'resolved_runtime',
        'total_episodes': 'resolved_total_episodes',
        'rating': 'resolved_vote_average',
        'vote_average': 'resolved_vote_average',
        'vote_count': 'resolved_vote_count',
        'added_at': 'added_at',
        'progress_percent': 'resolved_progress_percent',
        'episodes_left': 'resolved_episodes_left',
        'time_left': 'resolved_time_left',
    }
    field_name = field_by_sort.get(sort_key, 'added_at')

    if direction == 'desc':
        return queryset.order_by(F(field_name).desc(nulls_last=True), 'resolved_title', id_order)
    return queryset.order_by(F(field_name).asc(nulls_last=True), 'resolved_title', id_order)


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
        qs = WatchEntry.objects.filter(user=self.request.user)
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
        rating_rows = Rating.objects.filter(
            user=request.user,
        ).filter(
            Q(media_type=MediaType.MOVIE, tmdb_id__in=movie_ids)
            | Q(media_type=MediaType.TV, tmdb_id__in=show_ids)
        ).values('media_type', 'tmdb_id', 'score')
        rating_map = {(row['media_type'], row['tmdb_id']): row['score'] for row in rating_rows}

        context = self.get_serializer_context()
        context.update({'movie_map': movie_map, 'tv_map': tv_map})
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

    def perform_create(self, serializer):
        watched_at = serializer.validated_data.get('watched_at')
        if not watched_at:
            watched_at = timezone.now()
        instance = serializer.save(user=self.request.user, watched_at=watched_at)
        if instance.media_type == WatchEntryMediaType.MOVIE:
            UserMediaStatus.objects.clear_planning(instance.user, MediaType.MOVIE, instance.tmdb_id)
        elif instance.media_type == WatchEntryMediaType.EPISODE:
            UserMediaStatus.objects.clear_planning(instance.user, MediaType.TV, instance.tmdb_id)


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
            ).exists()
        else:
            can_rate = UserMediaStatus.objects.shows().filter(
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
            'rating', 'runtime', 'total_episodes', 'vote_count',
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
            ).exists()
        else:
            # For TV shows, check if any episodes watched
            watched = UserMediaStatus.objects.shows().filter(
                user=self.request.user,
                tmdb_id=tmdb_id,
                status__in=(TvShowStatus.WATCHING, TvShowStatus.WATCHED),
                watched_episodes__gt=0,
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
        defaults={'watched_at': watched_at}
    )
    if not created:
        entry.watched_at = watched_at
        entry.save(update_fields=['watched_at'])

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
            watched_at=watched_at
        ))
    
    WatchEntry.objects.bulk_create(
        entries,
        ignore_conflicts=True
    )

    from .cache import cache
    for ep in episodes:
        cache.mark_episode_watched(request.user.id, tmdb_id, season_number, ep['episode_number'])

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


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def unmark_show_watched(request):
    """Unmark all watched episodes in a show."""
    tmdb_id = request.data.get('tmdb_id')

    if not tmdb_id:
        return Response({'detail': 'tmdb_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

    tmdb_id = _coerce_int(tmdb_id, 'tmdb_id')

    count, _ = WatchEntry.objects.filter(
        user=request.user,
        media_type=WatchEntryMediaType.EPISODE,
        tmdb_id=tmdb_id,
    ).delete()

    return Response({'unmarked': count})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def up_next(request):
    """Get next episodes for currently watching shows."""
    from django.utils import timezone
    from media.models import Episode, TVShow

    today = timezone.now().date()

    watched_episode_exists = WatchEntry.objects.filter(
        user=request.user,
        media_type=WatchEntryMediaType.EPISODE,
        tmdb_id=OuterRef('season__show__tmdb_id'),
        season_number=OuterRef('season__season_number'),
        episode_number=OuterRef('episode_number'),
    )

    unwatched_aired_episodes = Episode.objects.filter(
        season__show__tmdb_id=OuterRef('tmdb_id'),
        season__season_number__gt=0,
        air_date__lte=today,
    ).filter(~Exists(watched_episode_exists))

    next_episode = unwatched_aired_episodes.order_by('season__season_number', 'episode_number')
    episodes_left_subquery = unwatched_aired_episodes.values('season__show__tmdb_id').annotate(
        total=Count('id')
    ).values('total')[:1]
    runtime_left_subquery = unwatched_aired_episodes.values('season__show__tmdb_id').annotate(
        total=Coalesce(Sum('runtime'), Value(0))
    ).values('total')[:1]
    unknown_runtime_subquery = unwatched_aired_episodes.values('season__show__tmdb_id').annotate(
        total=Count('id', filter=Q(runtime__isnull=True))
    ).values('total')[:1]

    watched_show_ids = UserMediaStatus.objects.shows().filter(
        user=request.user,
        status__in=(TvShowStatus.WATCHING, TvShowStatus.WATCHED),
        watched_episodes__gt=0,
    ).annotate(
        next_season_number=Subquery(next_episode.values('season__season_number')[:1]),
        next_episode_number=Subquery(next_episode.values('episode_number')[:1]),
        next_episode_name=Subquery(next_episode.values('name')[:1]),
        next_still_path=Subquery(next_episode.values('still_path')[:1]),
        next_air_date=Subquery(next_episode.values('air_date')[:1]),
        next_runtime=Subquery(next_episode.values('runtime')[:1]),
        next_episode_type=Subquery(next_episode.values('episode_type')[:1]),
        episodes_left=Coalesce(Subquery(episodes_left_subquery), Value(0), output_field=IntegerField()),
        runtime_left_minutes=Coalesce(Subquery(runtime_left_subquery), Value(0), output_field=IntegerField()),
        unknown_runtime_count=Coalesce(Subquery(unknown_runtime_subquery), Value(0), output_field=IntegerField()),
    ).filter(
        next_season_number__isnull=False,
    ).values(
        'tmdb_id',
        'last_watched_at',
        'progress_percent',
        'next_season_number',
        'next_episode_number',
        'next_episode_name',
        'next_still_path',
        'next_air_date',
        'next_runtime',
        'next_episode_type',
        'episodes_left',
        'runtime_left_minutes',
        'unknown_runtime_count',
    ).order_by('-last_watched_at', '-tmdb_id')

    watched_show_rows = list(watched_show_ids)

    shows_by_tmdb_id = {
        show.tmdb_id: show
        for show in TVShow.objects.filter(tmdb_id__in=[item['tmdb_id'] for item in watched_show_rows]).only('tmdb_id', 'name', 'poster_path')
    }

    up_next_data = []
    new_threshold = today - timedelta(days=7)
    for show_item in watched_show_rows:
        show = shows_by_tmdb_id.get(show_item['tmdb_id'])
        if show is None:
            continue
        progress_percent = show_item.get('progress_percent')
        up_next_data.append({
            'tmdb_id': show_item['tmdb_id'],
            'show_name': show.name,
            'poster_path': show.poster_path,
            'poster_url': show.poster_url,
            'last_watched_at': show_item['last_watched_at'],
            'progress_percent': progress_percent if progress_percent is not None else 0,
            'episodes_left': show_item['episodes_left'],
            'runtime_left_minutes': show_item['runtime_left_minutes'],
            'runtime_left_has_unknown': show_item['unknown_runtime_count'] > 0,
            'next_episode': {
                'season_number': show_item['next_season_number'],
                'episode_number': show_item['next_episode_number'],
                'name': show_item['next_episode_name'],
                'still_path': show_item['next_still_path'],
                'still_url': f"https://image.tmdb.org/t/p/w300{show_item['next_still_path']}" if show_item['next_still_path'] else None,
                'air_date': show_item['next_air_date'],
                'runtime': show_item['next_runtime'],
                'episode_type': show_item['next_episode_type'],
            }
        })

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


def _apply_progress_filters(items, request):
    params = request.query_params
    search = (params.get('search') or '').strip().lower()
    status_values = {value.lower() for value in _parse_multi_param(params, 'status')}
    provider_status_values = {value.lower() for value in _parse_multi_param(params, 'provider_status')}
    selected_genres = {value.lower() for value in _parse_multi_param(params, 'genres')}
    has_upcoming = _parse_bool_param(params.get('has_upcoming'))
    is_new = _parse_bool_param(params.get('is_new'))
    missing_rating = _parse_bool_param(params.get('missing_rating'))

    filtered = []
    for item in items:
        if search and search not in item['show_name'].lower():
            continue
        if status_values:
            status_match = False
            for status_value in status_values:
                if status_value == 'watching':
                    if item['status'] == 'watching' and (item.get('episodes_left') or 0) > 0:
                        status_match = True
                        break
                    continue

                if status_value in ('watched', 'completed', 'complete'):
                    if (item.get('progress_percent') or 0) >= 100:
                        status_match = True
                        break
                    continue

                if item['status'] == status_value:
                    status_match = True
                    break

            if not status_match:
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
        filtered.append(item)
    return filtered


def _sort_progress_items(items, sort_by: str, direction: str):
    sort_key = (sort_by or 'time_left').strip().lower()
    direction_key = (direction or '').strip().lower()
    default_direction_by_sort = {
        'last_watched': 'desc',
        'release_date': 'desc',
        'next_episode_date': 'desc',
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

    watched_episode_exists = WatchEntry.objects.filter(
        user=request.user,
        media_type=WatchEntryMediaType.EPISODE,
        tmdb_id=OuterRef('season__show__tmdb_id'),
        season_number=OuterRef('season__season_number'),
        episode_number=OuterRef('episode_number'),
    )

    unwatched_aired_episodes = Episode.objects.filter(
        season__show__tmdb_id=OuterRef('tmdb_id'),
        season__season_number__gt=0,
        air_date__lte=today,
    ).filter(~Exists(watched_episode_exists))

    next_episode = unwatched_aired_episodes.order_by('season__season_number', 'episode_number')
    episodes_left_subquery = unwatched_aired_episodes.values('season__show__tmdb_id').annotate(
        total=Count('id')
    ).values('total')[:1]
    runtime_left_subquery = unwatched_aired_episodes.values('season__show__tmdb_id').annotate(
        total=Coalesce(Sum('runtime'), Value(0))
    ).values('total')[:1]
    unknown_runtime_subquery = unwatched_aired_episodes.values('season__show__tmdb_id').annotate(
        total=Count('id', filter=Q(runtime__isnull=True))
    ).values('total')[:1]

    upcoming_episode = Episode.objects.filter(
        season__show__tmdb_id=OuterRef('tmdb_id'),
        season__season_number__gt=0,
        air_date__gt=today,
    ).order_by('air_date', 'season__season_number', 'episode_number')

    started_statuses = (TvShowStatus.WATCHING, TvShowStatus.WATCHED, TvShowStatus.DROPPED)
    oldest_watched_episode = WatchEntry.objects.filter(
        user=request.user,
        media_type=WatchEntryMediaType.EPISODE,
        tmdb_id=OuterRef('tmdb_id'),
    ).annotate(
        event_at=Coalesce('watched_at', 'created_at', output_field=DateTimeField())
    ).order_by('event_at', 'id')

    latest_watched_episode = WatchEntry.objects.filter(
        user=request.user,
        media_type=WatchEntryMediaType.EPISODE,
        tmdb_id=OuterRef('tmdb_id'),
        season_number__isnull=False,
        episode_number__isnull=False,
    ).annotate(
        event_at=Coalesce('watched_at', 'created_at', output_field=DateTimeField())
    ).order_by('-event_at', '-id')

    status_tmdb_ids = set(
        UserMediaStatus.objects.shows().filter(
            user=request.user,
            status__in=started_statuses,
        ).values_list('tmdb_id', flat=True)
    )
    watchlist_tmdb_ids = set(
        UserMediaStatus.objects.for_user(request.user).shows().planning().values_list('tmdb_id', flat=True)
    )
    progress_tmdb_ids = status_tmdb_ids | watchlist_tmdb_ids

    status_rows = list(
        UserMediaStatus.objects.shows().filter(
            user=request.user,
            tmdb_id__in=status_tmdb_ids,
            status__in=started_statuses,
        ).annotate(
            next_season_number=Subquery(next_episode.values('season__season_number')[:1]),
            next_episode_number=Subquery(next_episode.values('episode_number')[:1]),
            next_episode_name=Subquery(next_episode.values('name')[:1]),
            next_still_path=Subquery(next_episode.values('still_path')[:1]),
            next_air_date=Subquery(next_episode.values('air_date')[:1]),
            next_runtime=Subquery(next_episode.values('runtime')[:1]),
            next_episode_type=Subquery(next_episode.values('episode_type')[:1]),
            next_vote_average=Subquery(next_episode.values('vote_average')[:1]),
            next_vote_count=Subquery(next_episode.values('vote_count')[:1]),
            episodes_left=Coalesce(Subquery(episodes_left_subquery), Value(0), output_field=IntegerField()),
            runtime_left_minutes=Coalesce(Subquery(runtime_left_subquery), Value(0), output_field=IntegerField()),
            unknown_runtime_count=Coalesce(Subquery(unknown_runtime_subquery), Value(0), output_field=IntegerField()),
            upcoming_season_number=Subquery(upcoming_episode.values('season__season_number')[:1]),
            upcoming_episode_number=Subquery(upcoming_episode.values('episode_number')[:1]),
            upcoming_episode_name=Subquery(upcoming_episode.values('name')[:1]),
            upcoming_episode_type=Subquery(upcoming_episode.values('episode_type')[:1]),
            upcoming_air_date=Subquery(upcoming_episode.values('air_date')[:1]),
            started_watch_at=Subquery(oldest_watched_episode.values('event_at')[:1]),
            last_watched_season_number=Subquery(latest_watched_episode.values('season_number')[:1]),
            last_watched_episode_number=Subquery(latest_watched_episode.values('episode_number')[:1]),
        ).values(
            'tmdb_id',
            'status',
            'progress_percent',
            'last_watched_at',
            'started_at',
            'watched_episodes',
            'total_episodes',
            'next_season_number',
            'next_episode_number',
            'next_episode_name',
            'next_still_path',
            'next_air_date',
            'next_runtime',
            'next_episode_type',
            'next_vote_average',
            'next_vote_count',
            'episodes_left',
            'runtime_left_minutes',
            'unknown_runtime_count',
            'upcoming_season_number',
            'upcoming_episode_number',
            'upcoming_episode_name',
            'upcoming_episode_type',
            'upcoming_air_date',
            'started_watch_at',
            'last_watched_season_number',
            'last_watched_episode_number',
        )
    )

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
                'total_watched_minutes': 0,
            })
        response = paginator.get_paginated_response(page)
        response.data['available_genres'] = []
        response.data['available_provider_statuses'] = []
        response.data['total_watched_minutes'] = 0
        return response

    status_row_by_tmdb_id = {row['tmdb_id']: row for row in status_rows}
    tmdb_ids = list(progress_tmdb_ids)
    watched_runtime_subquery = Episode.objects.filter(
        season__show__tmdb_id=OuterRef('tmdb_id'),
        season__season_number=OuterRef('season_number'),
        episode_number=OuterRef('episode_number'),
    ).values('runtime')[:1]
    watched_runtime_entries = WatchEntry.objects.filter(
        user=request.user,
        media_type=WatchEntryMediaType.EPISODE,
        tmdb_id__in=tmdb_ids,
        season_number__isnull=False,
        episode_number__isnull=False,
    ).annotate(
        runtime=Coalesce(Subquery(watched_runtime_subquery, output_field=IntegerField()), Value(0))
    )
    watched_runtime_by_show = {
        row['tmdb_id']: row['total_runtime'] or 0
        for row in watched_runtime_entries.values('tmdb_id').annotate(
            total_runtime=Coalesce(Sum('runtime'), Value(0), output_field=IntegerField())
        )
    }

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
        is_plan_to_watch_only = row is None

        raw_networks = [part.strip() for part in (show.networks or '').split(',') if part.strip()]
        next_air_date = row.get('next_air_date') if row else None
        is_new = bool(next_air_date and new_threshold <= next_air_date <= today)
        item = {
            'tmdb_id': tmdb_id,
            'show_name': show.name,
            'release_date': show.first_air_date,
            'poster_path': show.poster_path,
            'poster_url': show.poster_url,
            'number_of_seasons': show.number_of_seasons,
            'status': 'plan_to_watch' if is_plan_to_watch_only else row['status'],
            'provider_status': show.status,
            'user_rating': rating_map.get(tmdb_id),
            'vote_average': show.vote_average,
            'vote_count': show.vote_count,
            'genres': [genre.name for genre in show.genres.all()],
            'networks': raw_networks,
            'episode_runtime': show.episode_runtime,
        }

        if not is_plan_to_watch_only:
            item.update({
                'progress_percent': row['progress_percent'] or 0,
                'watched_episodes': row['watched_episodes'] or 0,
                'total_episodes': row['total_episodes'] or 0,
                'last_watched_at': row['last_watched_at'],
                'started_at': row['started_watch_at'] or row['started_at'],
                'episodes_left': row['episodes_left'] or 0,
                'runtime_left_minutes': row['runtime_left_minutes'] or 0,
                'runtime_left_has_unknown': (row['unknown_runtime_count'] or 0) > 0,
                'is_new': is_new,
                'has_upcoming_episode': row['upcoming_air_date'] is not None,
                'next_episode': {
                    'season_number': row['next_season_number'],
                    'episode_number': row['next_episode_number'],
                    'name': row['next_episode_name'],
                    'still_path': row['next_still_path'],
                    'still_url': f"https://image.tmdb.org/t/p/w300{row['next_still_path']}" if row['next_still_path'] else None,
                    'air_date': row['next_air_date'],
                    'runtime': row['next_runtime'],
                    'episode_type': row['next_episode_type'],
                    'vote_average': row['next_vote_average'],
                    'vote_count': row['next_vote_count'],
                },
                'upcoming_episode': {
                    'season_number': row['upcoming_season_number'],
                    'episode_number': row['upcoming_episode_number'],
                    'name': row['upcoming_episode_name'],
                    'episode_type': row['upcoming_episode_type'],
                    'air_date': row['upcoming_air_date'],
                },
                'last_watched_episode': {
                    'season_number': row['last_watched_season_number'],
                    'episode_number': row['last_watched_episode_number'],
                },
            })

        progress_items.append(item)

    available_genres = sorted({genre for item in progress_items for genre in item['genres']})
    available_provider_statuses = sorted({
        str(item['provider_status']).strip()
        for item in progress_items
        if str(item.get('provider_status') or '').strip()
    })

    filtered = _apply_progress_filters(progress_items, request)
    sorted_items = _sort_progress_items(filtered, request.query_params.get('sort'), request.query_params.get('direction'))
    total_watched_minutes = sum(watched_runtime_by_show.get(item['tmdb_id'], 0) for item in filtered)

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
            'total_watched_minutes': total_watched_minutes,
        })
    response = paginator.get_paginated_response(page)
    response.data['available_genres'] = available_genres
    response.data['available_provider_statuses'] = available_provider_statuses
    response.data['total_watched_minutes'] = total_watched_minutes
    return response


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def upcoming(request):
    """Get next UPCOMING episode for shows user is watching. Only one per show, max 5."""
    from django.utils import timezone
    from media.models import Episode

    shows_with_episodes = UserMediaStatus.objects.shows().filter(
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
            'episode_type': ep.episode_type,
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
    UserMediaStatus.objects.update_or_create(
        user=request.user,
        media_type=MediaType.TV,
        tmdb_id=tmdb_id,
        defaults={
            'status': TvShowStatus.DROPPED,
            'dropped_at': dropped_at,
            'status_changed_at': dropped_at,
        },
    )

    UserMediaStatus.objects.clear_planning(request.user, MediaType.TV, tmdb_id)

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

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        payload = dict(serializer.data)

        items_qs = ListItem.objects.filter(custom_list=instance).select_related('custom_list')
        from media.models import Movie, TVShow

        movie_ids = [entry.tmdb_id for entry in items_qs if entry.media_type == MediaType.MOVIE]
        tv_ids = [entry.tmdb_id for entry in items_qs if entry.media_type == MediaType.TV]
        movie_map = {m.tmdb_id: m for m in Movie.objects.filter(tmdb_id__in=movie_ids)}
        tv_map = {s.tmdb_id: s for s in TVShow.objects.filter(tmdb_id__in=tv_ids)}
        status_map = annotate_media_user_status(
            request.user,
            [{'media_type': entry.media_type, 'tmdb_id': entry.tmdb_id} for entry in items_qs],
        )

        item_context = self.get_serializer_context()
        item_context.update({'movie_map': movie_map, 'tv_map': tv_map, 'status_map': status_map})
        payload['items'] = ListItemSerializer(items_qs, many=True, context=item_context).data
        return Response(payload)


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

        media_type = (self.request.query_params.get('media_type') or '').strip().lower()
        if media_type in (MediaType.MOVIE, MediaType.TV):
            queryset = queryset.filter(media_type=media_type)

        # Search by title
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            from media.models import Movie, TVShow
            movie_ids = Movie.objects.filter(title__icontains=search).values_list('tmdb_id', flat=True)
            tv_ids = TVShow.objects.filter(name__icontains=search).values_list('tmdb_id', flat=True)
            queryset = queryset.filter(
                Q(media_type=MediaType.MOVIE, tmdb_id__in=movie_ids) |
                Q(media_type=MediaType.TV, tmdb_id__in=tv_ids)
            ).distinct()

        selected_genres = _parse_multi_param(self.request.query_params, 'genres')
        if selected_genres:
            from media.models import Movie, TVShow
            movie_ids = Movie.objects.filter(genres__name__in=selected_genres).values_list('tmdb_id', flat=True)
            tv_ids = TVShow.objects.filter(genres__name__in=selected_genres).values_list('tmdb_id', flat=True)
            queryset = queryset.filter(
                Q(media_type=MediaType.MOVIE, tmdb_id__in=movie_ids)
                | Q(media_type=MediaType.TV, tmdb_id__in=tv_ids)
            ).distinct()

        selected_statuses = _parse_multi_param(self.request.query_params, 'status')
        if selected_statuses:
            queryset = _apply_status_filter(queryset, self.request.user, selected_statuses)

        missing_rating = _parse_bool_param(self.request.query_params.get('missing_rating'))
        if missing_rating is True:
            queryset = _apply_missing_rating_filter(queryset, self.request.user)

        in_watchlist = _parse_bool_param(self.request.query_params.get('in_watchlist'))
        if in_watchlist is True:
            queryset = _apply_in_watchlist_filter(queryset, self.request.user)

        sort_key, direction = _normalize_sort(
            self.request.query_params.get('sort'),
            self.request.query_params.get('direction'),
            default_sort='added_at',
            default_direction='asc',
        )
        valid_sorts = {
            'added_at', 'title', 'release_date',
            'rating', 'runtime', 'total_episodes', 'vote_count',
            'watched_date', 'started_date', 'last_watched', 'progress_percent', 'episodes_left', 'time_left', 'next_episode_date'
        }
        if sort_key not in valid_sorts:
            sort_key = 'added_at'

        queryset = _apply_secondary_title_ordering(queryset, sort_key, direction, user=self.request.user)
        return queryset

    def perform_create(self, serializer):
        list_id = self.kwargs.get('list_id')
        custom_list = CustomList.objects.get(id=list_id)
        is_owner = custom_list.user_id == self.request.user.id
        is_collaborator = ListCollaborator.objects.filter(custom_list=custom_list, user=self.request.user).exists()
        if not (is_owner or is_collaborator):
            raise PermissionDenied('You can only add items to your lists or lists where you collaborate.')
        try:
            serializer.save(custom_list=custom_list)
        except IntegrityError:
            raise ValidationError({'detail': 'Item is already in this list.'})

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

        supported_sources = supported_import_sources()
        if not source:
            raise ValidationError({'source': f"source is required ({', '.join(supported_sources)})."})
        expected_format = expected_format_for_source(source)
        if expected_format is None:
            raise ValidationError({'source': f"source must be {', '.join(supported_sources)}"})
        if fmt != expected_format:
            raise ValidationError({'format': f'format must be {expected_format} for source={source}.'})

        job = DataTransferJob.objects.create(
            user=request.user,
            job_type=DataTransferJobType.IMPORT,
            data_format=fmt,
            status=DataTransferStatus.PENDING,
            input_file=uploaded,
            source=source,
            import_mode=DataImportMode.NEW_ITEMS,
        )

        if source == 'trakt':
            from .tasks import prepare_trakt_zip_import

            prepare_trakt_zip_import.delay(job.id)
        elif source == 'yamtrack':
            from .tasks import prepare_yamtrack_csv_import

            prepare_yamtrack_csv_import.delay(job.id)
        elif source == 'arxmedia':
            from .tasks import prepare_arxmedia_json_import

            prepare_arxmedia_json_import.delay(job.id)
        else:
            _raise_import_error(ImportErrorCode.IMPORT_SOURCE_UNSUPPORTED, 'Unsupported import source configuration.')
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
            _raise_import_error(ImportErrorCode.IMPORT_JOB_NOT_FOUND, 'Import job not found.')

        import_mode = (request.data.get('import_mode') or '').strip().lower()
        try:
            ConfirmImportCommand(job, import_mode).execute()
        except ImportDomainError as exc:
            raise_import_validation_error(exc)

        if job.source == 'trakt':
            from .tasks import apply_trakt_zip_import

            apply_trakt_zip_import.delay(job.id)
        elif job.source == 'yamtrack':
            from .tasks import apply_yamtrack_csv_import

            apply_yamtrack_csv_import.delay(job.id)
        elif job.source == 'arxmedia':
            from .tasks import apply_arxmedia_json_import

            apply_arxmedia_json_import.delay(job.id)
        else:
            _raise_import_error(ImportErrorCode.IMPORT_SOURCE_UNSUPPORTED, 'Unsupported import source configuration.')
        serializer = self.get_serializer(job, context={'request': request})
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)


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
        ).values_list('tmdb_id', flat=True)
    )
    watchlist_movies = set(
        UserMediaStatus.objects.for_user(request.user).movies().planning().values_list('tmdb_id', flat=True)
    )
    watchlist_tv = set(
        UserMediaStatus.objects.for_user(request.user).shows().planning().values_list('tmdb_id', flat=True)
    )

    excluded_movies = watched_movies | watchlist_movies
    excluded_tv = watched_tv | watchlist_tv

    history_count = WatchEntry.objects.filter(user=request.user).count()

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

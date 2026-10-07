import logging

from django.db.models import (
    Case,
    DateField,
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
from rest_framework.exceptions import ValidationError

from ..choices import (
    MediaType,
    TvShowStatus,
    WatchEntryMediaType,
)
from ..models import (
    Rating,
    UserMediaStatus,
    WatchEntry,
)
from ..query_helpers import media_ids_q

logger = logging.getLogger(__name__)



def _coerce_int(value, field_name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError({field_name: f'{field_name} must be an integer.'})


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


def _user_status_exists(user, media_type: str, status: str):
    return Exists(
        UserMediaStatus.objects.for_user(user).filter(media_type=media_type, status=status, tmdb_id=OuterRef('tmdb_id'))
    )


def _apply_status_filter(queryset, user, selected_statuses: list[str]):
    normalized = {value.strip().lower() for value in selected_statuses if value and value.strip()}
    if not normalized:
        return queryset

    # Correlated EXISTS checks keep the whole filter in one SQL query (no id lists round-tripped through Python).
    status_q = Q()
    if 'plan_to_watch' in normalized:
        status_q |= Q(_user_status_exists(user, MediaType.MOVIE, TvShowStatus.PLAN_TO_WATCH), media_type=MediaType.MOVIE)
        status_q |= Q(_user_status_exists(user, MediaType.TV, TvShowStatus.PLAN_TO_WATCH), media_type=MediaType.TV)
    if 'watching' in normalized:
        status_q |= Q(_user_status_exists(user, MediaType.TV, TvShowStatus.WATCHING), media_type=MediaType.TV)
    if 'watched' in normalized:
        movie_watched = Exists(
            WatchEntry.objects.filter(user=user, media_type=WatchEntryMediaType.MOVIE, tmdb_id=OuterRef('tmdb_id'))
        )
        status_q |= Q(movie_watched, media_type=MediaType.MOVIE)
        status_q |= Q(_user_status_exists(user, MediaType.TV, TvShowStatus.WATCHED), media_type=MediaType.TV)
    if 'dropped' in normalized:
        status_q |= Q(_user_status_exists(user, MediaType.TV, TvShowStatus.DROPPED), media_type=MediaType.TV)

    if not status_q:
        return queryset.none()
    return queryset.filter(status_q)


def _apply_missing_rating_filter(queryset, user):
    """Keep movies and shows the user has not rated, excluding ones still on their watchlist."""
    rated = Exists(Rating.objects.filter(user=user, media_type=OuterRef('media_type'), tmdb_id=OuterRef('tmdb_id')))
    planned = Exists(
        UserMediaStatus.objects.for_user(user).planning().filter(
            media_type=OuterRef('media_type'), tmdb_id=OuterRef('tmdb_id'),
        )
    )
    return queryset.filter(~rated, ~planned, media_type__in=(MediaType.MOVIE, MediaType.TV))


def _apply_in_watchlist_filter(queryset, user):
    movie_ids = UserMediaStatus.objects.for_user(user).movies().planning().values_list('tmdb_id', flat=True)
    tv_ids = UserMediaStatus.objects.for_user(user).shows().planning().values_list('tmdb_id', flat=True)
    return queryset.filter(
        media_ids_q(movie_ids, tv_ids)
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


def _compute_mixed_runtime_and_counts(queryset):
    from media.models import Movie

    movie_ids, tv_ids = _collect_media_ids(queryset)
    movie_runtime = 0
    if movie_ids:
        movie_runtime = Movie.objects.filter(tmdb_id__in=movie_ids).aggregate(total=Sum('runtime'))['total'] or 0

    tv_runtime = sum(_build_tv_runtime_map(list(tv_ids)).values())
    counts = {
        'movies': queryset.filter(media_type=MediaType.MOVIE).count(),
        'shows': queryset.filter(media_type=MediaType.TV).count(),
    }
    return int(movie_runtime) + int(tv_runtime), counts


def _normalize_sort(sort_raw: str | None, direction_raw: str | None, default_sort: str, default_direction: str) -> tuple[str, str]:
    sort_value = (sort_raw or default_sort).strip().lower()
    direction = (direction_raw or '').strip().lower()

    if sort_value.startswith('-'):
        sort_value = sort_value[1:]
        direction = 'desc'

    if direction not in ('asc', 'desc'):
        direction = default_direction

    return sort_value, direction


def _alias_media_sort_fields(queryset, user=None):
    from media.models import Episode, Movie, TVShow

    movie_lookup = Movie.objects.filter(tmdb_id=OuterRef('tmdb_id'))
    tv_lookup = TVShow.objects.filter(tmdb_id=OuterRef('tmdb_id'))

    tv_status_lookup = UserMediaStatus.objects.none()
    movie_watch_lookup = WatchEntry.objects.none()
    rating_lookup = Rating.objects.none()
    if user and user.is_authenticated:
        tv_status_lookup = UserMediaStatus.objects.shows().filter(user=user, tmdb_id=OuterRef('tmdb_id'))
        movie_watch_lookup = WatchEntry.objects.filter(
            user=user,
            media_type=WatchEntryMediaType.MOVIE,
            tmdb_id=OuterRef('tmdb_id'),
        ).order_by(F('watched_at').desc(nulls_last=True), '-id')
        rating_lookup = Rating.objects.filter(
            user=user,
            media_type=OuterRef('media_type'),
            tmdb_id=OuterRef('tmdb_id'),
        )

    today = timezone.now().date()

    # alias() keeps these out of SELECT: only the expressions the chosen ordering references reach the SQL.
    annotated = queryset.alias(
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
        tv_episodes_left=Subquery(tv_status_lookup.values('episodes_left')[:1]),
        tv_time_left_minutes=Subquery(tv_status_lookup.values('time_left_minutes')[:1]),
        tv_next_episode_date=Subquery(
            Episode.objects.filter(
                season__show__tmdb_id=OuterRef('tmdb_id'),
                season__season_number__gt=0,
                air_date__gte=today,
            ).order_by('air_date', 'season__season_number', 'episode_number').values('air_date')[:1]
        ),
        movie_watched_date=Subquery(movie_watch_lookup.values('watched_at')[:1]),
    ).alias(
        resolved_title=Lower(Coalesce('movie_title', 'tv_title', Value(''))),
        resolved_date=Coalesce('movie_release_date', 'tv_first_air_date'),
        resolved_runtime=Coalesce('movie_runtime', 'tv_total_runtime'),
        resolved_total_episodes=Coalesce('movie_total_episodes', 'tv_total_episodes'),
        resolved_vote_average=Case(
            When(media_type=MediaType.MOVIE, then=Coalesce('movie_vote_average', Value(0.0))),
            default=Coalesce('tv_vote_average', Value(0.0)),
        ),
        resolved_user_rating=Coalesce(
            Subquery(rating_lookup.values('score')[:1]),
            Value(0),
            output_field=IntegerField(),
        ),
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
            Coalesce('tv_episodes_left', Value(0)),
            output_field=IntegerField(),
        ),
        resolved_next_episode_date=Coalesce('tv_next_episode_date', Value(None, output_field=DateField())),
    )

    return annotated.alias(
        resolved_time_left=ExpressionWrapper(
            Coalesce('tv_time_left_minutes', Value(0)),
            output_field=IntegerField(),
        ),
    )


def _apply_secondary_title_ordering(queryset, sort_key: str, direction: str, id_desc: bool = False, user=None):
    if sort_key == 'custom_order':
        if direction == 'desc':
            return queryset.order_by(F('custom_order').desc(nulls_last=True), 'id')
        return queryset.order_by(F('custom_order').asc(nulls_last=True), 'id')

    queryset = _alias_media_sort_fields(queryset, user=user)

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
        'provider_rating': 'resolved_vote_average',
        'user_rating': 'resolved_user_rating',
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


def _ensure_local_metadata(media_type: str, tmdb_id: int) -> None:
    """Sync catalog metadata from TMDB only when the item is not stored locally yet."""
    from media.models import Movie, TVShow

    try:
        if media_type == MediaType.MOVIE and not Movie.objects.filter(tmdb_id=tmdb_id).exists():
            tmdb.sync_movie(tmdb_id)
        elif media_type == MediaType.TV and not TVShow.objects.filter(tmdb_id=tmdb_id).exists():
            tmdb.sync_tv_show(tmdb_id)
    except Exception as exc:
        logger.warning('Failed to sync %s metadata for tmdb_id=%s: %s', media_type, tmdb_id, exc)

from django.db.models import Count, DateTimeField, Max, Min
from django.db.models.functions import Coalesce

from media.models import Episode, TVShow

from .choices import MediaType, SeasonStatus, TvShowStatus, WatchEntryMediaType, WatchEntryStatus
from .models import UserSeasonStatus, UserTvShowStatus, WatchEntry, Watchlist


FINAL_TV_STATUSES = {'ended', 'canceled', 'cancelled'}


def _percent(watched_count: int, total_count: int) -> int:
    if total_count <= 0:
        return 0
    return int(round((watched_count / total_count) * 100))


def _is_final_tmdb_show_status(tmdb_id: int) -> bool:
    status = TVShow.objects.filter(tmdb_id=tmdb_id).values_list('status', flat=True).first() or ''
    return status.strip().lower() in FINAL_TV_STATUSES


def refresh_show_status(user_id: int, tmdb_id: int):
    watched_data = WatchEntry.objects.filter(
        user_id=user_id,
        media_type=WatchEntryMediaType.EPISODE,
        status=WatchEntryStatus.WATCHED,
        tmdb_id=tmdb_id,
        season_number__gt=0,
    ).annotate(
        event_at=Coalesce('watched_at', 'created_at', output_field=DateTimeField())
    ).aggregate(
        watched_episodes=Count('id'),
        first_watched_at=Min('event_at'),
        last_watched_at=Max('event_at'),
    )
    watched_episodes = watched_data.get('watched_episodes') or 0
    first_watched_at = watched_data.get('first_watched_at')
    last_watched_at = watched_data.get('last_watched_at')

    total_episodes = Episode.objects.filter(
        season__show__tmdb_id=tmdb_id,
        season__season_number__gt=0,
    ).count()

    dropped_at = WatchEntry.objects.filter(
        user_id=user_id,
        media_type=WatchEntryMediaType.EPISODE,
        status=WatchEntryStatus.DROPPED,
        tmdb_id=tmdb_id,
        season_number__isnull=True,
        episode_number__isnull=True,
    ).annotate(
        event_at=Coalesce('watched_at', 'created_at', output_field=DateTimeField())
    ).aggregate(last_dropped_at=Max('event_at'))['last_dropped_at']

    plan_to_watch_at = Watchlist.objects.filter(
        user_id=user_id,
        media_type=MediaType.TV,
        tmdb_id=tmdb_id,
    ).aggregate(last_added=Max('added_at'))['last_added']

    is_final = _is_final_tmdb_show_status(tmdb_id)
    if watched_episodes > 0:
        if total_episodes == 0 and is_final:
            candidate_status = TvShowStatus.WATCHED
        elif watched_episodes >= total_episodes and is_final:
            candidate_status = TvShowStatus.WATCHED
        elif total_episodes == 0 and not is_final:
            candidate_status = TvShowStatus.WATCHING
        elif watched_episodes >= total_episodes and not is_final:
            candidate_status = TvShowStatus.WATCHING
        else:
            candidate_status = TvShowStatus.WATCHING
    elif plan_to_watch_at:
        candidate_status = TvShowStatus.PLAN_TO_WATCH
    else:
        candidate_status = TvShowStatus.NONE

    if dropped_at and (last_watched_at is None or last_watched_at <= dropped_at):
        status_value = TvShowStatus.DROPPED
        status_changed_at = dropped_at
    else:
        status_value = candidate_status
        if status_value == TvShowStatus.WATCHED:
            status_changed_at = last_watched_at
        elif status_value == TvShowStatus.WATCHING:
            status_changed_at = last_watched_at
        elif status_value == TvShowStatus.PLAN_TO_WATCH:
            status_changed_at = plan_to_watch_at
        else:
            status_changed_at = None

    completed_at = None
    if watched_episodes > 0 and is_final and (total_episodes == 0 or watched_episodes >= total_episodes):
        completed_at = last_watched_at

    UserTvShowStatus.objects.update_or_create(
        user_id=user_id,
        tmdb_id=tmdb_id,
        defaults={
            'status': status_value,
            'watched_episodes': watched_episodes,
            'total_episodes': total_episodes,
            'progress_percent': _percent(watched_episodes, total_episodes),
            'started_at': first_watched_at,
            'completed_at': completed_at,
            'dropped_at': dropped_at,
            'plan_to_watch_at': plan_to_watch_at,
            'last_watched_at': last_watched_at,
            'status_changed_at': status_changed_at,
        },
    )


def refresh_season_status(user_id: int, tmdb_id: int, season_number: int):
    watched_data = WatchEntry.objects.filter(
        user_id=user_id,
        media_type=WatchEntryMediaType.EPISODE,
        status=WatchEntryStatus.WATCHED,
        tmdb_id=tmdb_id,
        season_number=season_number,
    ).annotate(
        event_at=Coalesce('watched_at', 'created_at', output_field=DateTimeField())
    ).aggregate(
        watched_episodes=Count('id'),
        first_watched_at=Min('event_at'),
        last_watched_at=Max('event_at'),
    )
    watched_episodes = watched_data.get('watched_episodes') or 0
    first_watched_at = watched_data.get('first_watched_at')
    last_watched_at = watched_data.get('last_watched_at')

    total_episodes = Episode.objects.filter(
        season__show__tmdb_id=tmdb_id,
        season__season_number=season_number,
    ).count()

    is_final = _is_final_tmdb_show_status(tmdb_id)
    if watched_episodes > 0:
        if total_episodes == 0 and is_final:
            status_value = SeasonStatus.WATCHED
        elif watched_episodes >= total_episodes and is_final:
            status_value = SeasonStatus.WATCHED
        else:
            status_value = SeasonStatus.WATCHING
    else:
        status_value = SeasonStatus.NONE

    if status_value == SeasonStatus.WATCHED:
        status_changed_at = last_watched_at
    elif status_value == SeasonStatus.WATCHING:
        status_changed_at = last_watched_at
    else:
        status_changed_at = None

    completed_at = last_watched_at if status_value == SeasonStatus.WATCHED else None

    UserSeasonStatus.objects.update_or_create(
        user_id=user_id,
        tmdb_id=tmdb_id,
        season_number=season_number,
        defaults={
            'status': status_value,
            'watched_episodes': watched_episodes,
            'total_episodes': total_episodes,
            'progress_percent': _percent(watched_episodes, total_episodes),
            'started_at': first_watched_at,
            'completed_at': completed_at,
            'last_watched_at': last_watched_at,
            'status_changed_at': status_changed_at,
        },
    )


def refresh_show_and_season_statuses(user_id: int, tmdb_id: int, season_numbers: set[int] | None = None):
    if season_numbers:
        for season_number in season_numbers:
            if season_number is None:
                continue
            refresh_season_status(user_id, tmdb_id, int(season_number))
    refresh_show_status(user_id, tmdb_id)

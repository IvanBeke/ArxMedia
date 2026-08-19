from datetime import datetime

from django.db.models import Count, DateTimeField, Max, Min
from django.db.models.functions import Coalesce
from media.models import Episode, TVShow

from .choices import MediaType, TvShowStatus, WatchEntryMediaType
from .models import UserTvShowStatus, WatchEntry, Watchlist

FINAL_TV_STATUSES = {'ended', 'canceled', 'cancelled'}


def _percent(watched_count: int, total_count: int) -> int:
    if total_count <= 0:
        return 0
    return round((watched_count / total_count) * 100)


def _is_final_tmdb_show_status(tmdb_id: int) -> bool:
    status = TVShow.objects.filter(tmdb_id=tmdb_id).values_list('status', flat=True).first() or ''
    return status.strip().lower() in FINAL_TV_STATUSES


def refresh_show_status(user_id: int, tmdb_id: int):
    watched_data = WatchEntry.objects.filter(
        user_id=user_id,
        media_type=WatchEntryMediaType.EPISODE,
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

    dropped_at = UserTvShowStatus.objects.filter(
        user_id=user_id,
        tmdb_id=tmdb_id,
    ).values_list('dropped_at', flat=True).first()

    plan_to_watch_at = Watchlist.objects.filter(
        user_id=user_id,
        media_type=MediaType.TV,
        tmdb_id=tmdb_id,
    ).aggregate(last_added=Max('added_at'))['last_added']

    is_final = _is_final_tmdb_show_status(tmdb_id)
    if watched_episodes > 0:
        if total_episodes == 0 and is_final or watched_episodes >= total_episodes and is_final:
            candidate_status = TvShowStatus.WATCHED
        elif total_episodes == 0 and not is_final or watched_episodes >= total_episodes and not is_final:
            candidate_status = TvShowStatus.WATCHING
        else:
            candidate_status = TvShowStatus.WATCHING
    elif plan_to_watch_at:
        candidate_status = TvShowStatus.PLAN_TO_WATCH
    else:
        candidate_status = TvShowStatus.NONE

    status_changed_at: datetime | None = None
    if dropped_at and (last_watched_at is None or last_watched_at <= dropped_at):
        status_value = TvShowStatus.DROPPED
        status_changed_at = dropped_at
    else:
        status_value = candidate_status
        if status_value == TvShowStatus.WATCHED or status_value == TvShowStatus.WATCHING:
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


def refresh_all_statuses_for_show(tmdb_id: int, current_user_id: int | None = None):
    status_user_ids = set(
        UserTvShowStatus.objects.filter(
            tmdb_id=tmdb_id,
            status__in=(TvShowStatus.WATCHING, TvShowStatus.WATCHED, TvShowStatus.DROPPED),
        ).values_list('user_id', flat=True)
    )
    watch_entry_user_ids = set(
        WatchEntry.objects.filter(
            media_type=WatchEntryMediaType.EPISODE,
            tmdb_id=tmdb_id,
        ).values_list('user_id', flat=True)
    )
    user_ids = status_user_ids | watch_entry_user_ids

    if not user_ids:
        return

    remaining_user_ids = set(user_ids)
    if current_user_id is not None and current_user_id in user_ids:
        refresh_show_status(current_user_id, tmdb_id)
        remaining_user_ids.discard(current_user_id)

    if remaining_user_ids:
        from .tasks.system import refresh_show_status_for_user

        for user_id in remaining_user_ids:
            refresh_show_status_for_user.delay(tmdb_id, user_id)

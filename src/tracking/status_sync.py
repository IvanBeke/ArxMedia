from datetime import datetime
from functools import partial

from django.db import transaction
from django.db.models import Max, Min
from django.utils import timezone
from media.models import Episode, TVShow

from .choices import MediaType, TvShowStatus
from .models import UserMediaStatus, WatchEntry


def _percent(watched_count: int, total_count: int) -> int:
    if total_count <= 0:
        return 0
    return min(100, watched_count * 100 // total_count)


def rebuild_episode_chain(tmdb_id: int):
    episodes = list(
        Episode.objects.filter(season__show__tmdb_id=tmdb_id)
        .order_by('season__season_number', 'episode_number', 'id')
    )
    updates = []
    for index, episode in enumerate(episodes):
        next_episode_id = episodes[index + 1].id if index + 1 < len(episodes) else None
        if episode.next_episode_id != next_episode_id:
            episode.next_episode_id = next_episode_id
            updates.append(episode)
    if updates:
        Episode.objects.bulk_update(updates, ['next_episode'])

    return len(episodes)


def _released_episode_queryset(tmdb_id: int, now=None):
    now = now or timezone.now()
    return Episode.objects.filter(season__show__tmdb_id=tmdb_id).filter(Episode.released_q(now))


def _is_final_tmdb_show_status(tmdb_id: int) -> bool:
    status = TVShow.objects.filter(tmdb_id=tmdb_id).values_list('status', flat=True).first() or ''
    return status.strip().lower() in TVShow.FINAL_STATUSES


def calculate_show_progress(user_id: int, tmdb_id: int, now=None) -> dict:
    """Calculate progress from released catalog episodes and valid watch keys."""
    now = now or timezone.now()
    released_rows = list(_released_episode_queryset(tmdb_id, now).values(
        'id', 'season__season_number', 'episode_number', 'runtime',
    ))
    released_keys = {
        (row['season__season_number'], row['episode_number'])
        for row in released_rows
    }
    watched_keys = set(WatchEntry.objects.for_user(user_id).for_show(tmdb_id).filter(
        season_number__gt=0,
    ).values_list('season_number', 'episode_number'))
    valid_watched_keys = watched_keys & released_keys
    remaining_rows = [
        row for row in released_rows
        if (row['season__season_number'], row['episode_number']) not in valid_watched_keys
    ]
    return {
        'released_rows': released_rows,
        'valid_watched_keys': valid_watched_keys,
        'orphan_watched_keys': watched_keys - released_keys,
        'remaining_rows': remaining_rows,
        'watched_episodes': len(valid_watched_keys),
        'total_episodes': len(released_rows),
        'episodes_left': len(remaining_rows),
        'time_left_minutes': sum(row['runtime'] for row in remaining_rows if row['runtime'] is not None),
        'time_left_has_unknown': any(row['runtime'] is None for row in remaining_rows),
    }


def refresh_show_status(user_id: int, tmdb_id: int):
    existing = UserMediaStatus.objects.shows().filter(user_id=user_id, tmdb_id=tmdb_id).first()

    progress = calculate_show_progress(user_id, tmdb_id)
    remaining_rows = progress['remaining_rows']
    watched_episodes = progress['watched_episodes']
    has_watched_entries = bool(WatchEntry.objects.for_user(user_id).for_show(tmdb_id).filter(
        season_number__gt=0,
    ).exists())
    total_episodes = progress['total_episodes']
    time_left_minutes = progress['time_left_minutes']
    time_left_has_unknown = progress['time_left_has_unknown']
    watched_data = WatchEntry.objects.for_user(user_id).for_show(tmdb_id).filter(
        tmdb_id=tmdb_id,
        season_number__gt=0,
    ).with_event_at().aggregate(
        first_watched_at=Min('event_at'),
        last_watched_at=Max('event_at'),
    )
    first_watched_at = watched_data.get('first_watched_at')
    last_watched_at = watched_data.get('last_watched_at')

    dropped_at = existing.dropped_at if existing else None

    is_final = _is_final_tmdb_show_status(tmdb_id)
    if has_watched_entries:
        if total_episodes > 0 and watched_episodes >= total_episodes and is_final:
            candidate_status = TvShowStatus.WATCHED
        else:
            candidate_status = TvShowStatus.WATCHING
    else:
        candidate_status = None

    status_value: str | None = None
    status_changed_at: datetime | None = None
    if dropped_at and (last_watched_at is None or last_watched_at <= dropped_at):
        status_value = TvShowStatus.DROPPED
        status_changed_at = dropped_at
    else:
        status_value = candidate_status
        if status_value == TvShowStatus.WATCHED or status_value == TvShowStatus.WATCHING:
            status_changed_at = last_watched_at
        else:
            status_changed_at = None

    if status_value is None:
        if existing and existing.status == TvShowStatus.PLAN_TO_WATCH:
            UserMediaStatus.objects.filter(id=existing.id).update(
                watched_episodes=watched_episodes,
                total_episodes=total_episodes,
                progress_percent=_percent(watched_episodes, total_episodes),
                episodes_left=len(remaining_rows),
                time_left_minutes=time_left_minutes,
                time_left_has_unknown=time_left_has_unknown,
                started_at=first_watched_at,
                last_watched_at=last_watched_at,
                completed_at=None,
            )
            return
        UserMediaStatus.objects.filter(user_id=user_id, media_type=MediaType.TV, tmdb_id=tmdb_id).delete()
        return

    completed_at = None
    if watched_episodes > 0 and total_episodes > 0 and is_final and watched_episodes >= total_episodes:
        completed_at = last_watched_at

    UserMediaStatus.objects.update_or_create(
        user_id=user_id,
        media_type=MediaType.TV,
        tmdb_id=tmdb_id,
        defaults={
            'status': status_value,
            'watched_episodes': watched_episodes,
            'total_episodes': total_episodes,
            'progress_percent': _percent(watched_episodes, total_episodes),
            'episodes_left': len(remaining_rows),
            'time_left_minutes': time_left_minutes,
            'time_left_has_unknown': time_left_has_unknown,
            'started_at': first_watched_at,
            'completed_at': completed_at,
            'dropped_at': dropped_at,
            'last_watched_at': last_watched_at,
            'status_changed_at': status_changed_at,
        },
    )


def refresh_all_statuses_for_show(tmdb_id: int, current_user_id: int | None = None):
    status_user_ids = set(
        UserMediaStatus.objects.shows().started().filter(
            tmdb_id=tmdb_id,
            status__in=(TvShowStatus.WATCHING, TvShowStatus.WATCHED, TvShowStatus.DROPPED),
        ).values_list('user_id', flat=True)
    )
    planning_user_ids = set(UserMediaStatus.objects.shows().planning().filter(tmdb_id=tmdb_id).values_list('user_id', flat=True))
    watch_entry_user_ids = set(
        WatchEntry.objects.for_show(tmdb_id).values_list('user_id', flat=True)
    )
    user_ids = status_user_ids | watch_entry_user_ids | planning_user_ids

    if not user_ids:
        return

    remaining_user_ids = set(user_ids)
    if current_user_id is not None and current_user_id in user_ids:
        refresh_show_status(current_user_id, tmdb_id)
        remaining_user_ids.discard(current_user_id)

    if remaining_user_ids:
        from .tasks.system import refresh_show_status_for_user

        for user_id in remaining_user_ids:
            transaction.on_commit(partial(refresh_show_status_for_user.delay, tmdb_id, user_id))

import logging

from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from ..cache import cache
from ..choices import WatchEntryMediaType
from ..models import WatchEntry
from ..signals import suppress_watch_entry_delete_signals
from ..status_sync import refresh_show_status
from ._helpers import _coerce_int

logger = logging.getLogger(__name__)


def _refresh_after_bulk_change(user_id, tmdb_id):
    """Bulk writes skip (or suppress) per-row signals, so refresh cached stats and show status once."""
    cache.invalidate_user_stats(user_id)
    refresh_show_status(user_id, tmdb_id)


def _bulk_delete_episode_entries(user_id, tmdb_id, entries):
    with suppress_watch_entry_delete_signals():
        count, _ = entries.delete()
    if count:
        _refresh_after_bulk_change(user_id, tmdb_id)
    return count


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


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def mark_episode_watched(request):
    """Mark a single episode as watched."""
    tmdb_id = request.data.get('tmdb_id')
    season_number = request.data.get('season_number')
    episode_number = request.data.get('episode_number')
    watched_at_str = request.data.get('watched_at')

    if any(value is None for value in (tmdb_id, season_number, episode_number)):
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

    return Response({'id': entry.id, 'created': created}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def unmark_episode_watched(request):
    """Unmark a single episode as watched."""
    tmdb_id = request.data.get('tmdb_id')
    season_number = request.data.get('season_number')
    episode_number = request.data.get('episode_number')

    if any(value is None for value in (tmdb_id, season_number, episode_number)):
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

    if any(value is None for value in (tmdb_id, season_number)):
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

    _refresh_after_bulk_change(request.user.id, tmdb_id)

    watched_episodes = WatchEntry.objects.filter(
        user=request.user,
        media_type=WatchEntryMediaType.EPISODE,
        tmdb_id=tmdb_id,
        season_number=season_number,
    ).values('season_number', 'episode_number', 'watched_at')

    return Response({'marked': len(episodes), 'episodes': list(watched_episodes)})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def unmark_season_watched(request):
    """Unmark all episodes in a season."""
    tmdb_id = request.data.get('tmdb_id')
    season_number = request.data.get('season_number')

    if any(value is None for value in (tmdb_id, season_number)):
        return Response({'detail': 'tmdb_id and season_number are required.'}, status=status.HTTP_400_BAD_REQUEST)

    tmdb_id = _coerce_int(tmdb_id, 'tmdb_id')
    season_number = _coerce_int(season_number, 'season_number')

    entries = WatchEntry.objects.filter(
        user=request.user,
        media_type=WatchEntryMediaType.EPISODE,
        tmdb_id=tmdb_id,
        season_number=season_number
    )
    episodes = list(entries.values('season_number', 'episode_number', 'watched_at'))
    count = _bulk_delete_episode_entries(request.user.id, tmdb_id, entries)

    return Response({'unmarked': count, 'episodes': episodes})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def unmark_show_watched(request):
    """Unmark all watched episodes in a show."""
    tmdb_id = request.data.get('tmdb_id')

    if not tmdb_id:
        return Response({'detail': 'tmdb_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

    tmdb_id = _coerce_int(tmdb_id, 'tmdb_id')

    entries = WatchEntry.objects.filter(
        user=request.user,
        media_type=WatchEntryMediaType.EPISODE,
        tmdb_id=tmdb_id,
    )
    count = _bulk_delete_episode_entries(request.user.id, tmdb_id, entries)

    return Response({'unmarked': count})

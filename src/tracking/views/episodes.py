import logging

from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from ..cache import cache
from ..choices import WatchEntryMediaType
from ..models import WatchEntry
from ..signals import suppress_watch_entry_delete_signals
from ..status_sync import refresh_show_status
from ..watched_at import resolve_watched_at, wants_release_date
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


def _episode_release(episode_row):
    """Release moment of an episode row: exact broadcast time when known, otherwise its air date."""
    return episode_row.get('broadcast_start') or episode_row.get('air_date')


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def mark_episode_watched(request):
    """Mark a single episode as watched."""
    tmdb_id = request.data.get('tmdb_id')
    season_number = request.data.get('season_number')
    episode_number = request.data.get('episode_number')
    watched_at_value = request.data.get('watched_at')

    if any(value is None for value in (tmdb_id, season_number, episode_number)):
        return Response({'detail': 'tmdb_id, season_number, and episode_number are required.'}, status=status.HTTP_400_BAD_REQUEST)

    tmdb_id = _coerce_int(tmdb_id, 'tmdb_id')
    season_number = _coerce_int(season_number, 'season_number')
    episode_number = _coerce_int(episode_number, 'episode_number')

    release = None
    if wants_release_date(watched_at_value):
        from media.models import Episode

        release = _episode_release(
            Episode.objects.filter(
                season__show__tmdb_id=tmdb_id, season__season_number=season_number, episode_number=episode_number,
            ).values('broadcast_start', 'air_date').first() or {}
        )
    watched_at = resolve_watched_at(watched_at_value, release)

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

    return Response({'id': entry.id, 'created': created, 'watched_at': entry.watched_at}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


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


def _season_episode_rows(season):
    """Episode numbers and air dates for a season, syncing it from TMDB first if none are stored."""
    from media.models import Episode

    fields = ('episode_number', 'air_date', 'broadcast_start')
    rows = list(Episode.objects.filter(season=season).values(*fields))
    if not rows:
        from media.tmdb import tmdb
        try:
            tmdb.sync_season(season.show, season.season_number)
            rows = list(Episode.objects.filter(season=season).values(*fields))
        except Exception as exc:
            logger.warning('Failed to sync season %s for show %s: %s', season.season_number, season.show.tmdb_id, exc)
    return rows


def _bulk_mark_episodes(user, tmdb_id, rows_by_season, watched_at_value):
    """Create watch entries for (season_number, episode rows) pairs, refresh once, and return the count marked."""
    per_episode = wants_release_date(watched_at_value)
    shared_watched_at = None if per_episode else resolve_watched_at(watched_at_value)
    entries = []
    for season_number, rows in rows_by_season:
        for row in rows:
            watched_at = resolve_watched_at(watched_at_value, _episode_release(row)) if per_episode else shared_watched_at
            entries.append(WatchEntry(
                user=user,
                media_type=WatchEntryMediaType.EPISODE,
                tmdb_id=tmdb_id,
                season_number=season_number,
                episode_number=row['episode_number'],
                watched_at=watched_at,
            ))
    WatchEntry.objects.bulk_create(entries, ignore_conflicts=True)
    _refresh_after_bulk_change(user.id, tmdb_id)
    return len(entries)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def mark_season_watched(request):
    """Mark all episodes in a season as watched."""
    tmdb_id = request.data.get('tmdb_id')
    season_number = request.data.get('season_number')

    if any(value is None for value in (tmdb_id, season_number)):
        return Response({'detail': 'tmdb_id and season_number are required.'}, status=status.HTTP_400_BAD_REQUEST)

    tmdb_id = _coerce_int(tmdb_id, 'tmdb_id')
    season_number = _coerce_int(season_number, 'season_number')

    from media.models import Season
    season = Season.objects.filter(show__tmdb_id=tmdb_id, season_number=season_number).select_related('show').first()
    if season is None:
        return Response({'detail': 'Season not found.'}, status=status.HTTP_404_NOT_FOUND)

    marked = _bulk_mark_episodes(
        request.user, tmdb_id, [(season_number, _season_episode_rows(season))], request.data.get('watched_at'),
    )
    watched_episodes = WatchEntry.objects.filter(
        user=request.user,
        media_type=WatchEntryMediaType.EPISODE,
        tmdb_id=tmdb_id,
        season_number=season_number,
    ).values('season_number', 'episode_number', 'watched_at')

    return Response({'marked': marked, 'episodes': list(watched_episodes)})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def mark_show_watched(request):
    """Mark every episode of a show's regular seasons (specials excluded) as watched in one request."""
    tmdb_id = request.data.get('tmdb_id')
    if tmdb_id is None:
        return Response({'detail': 'tmdb_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
    tmdb_id = _coerce_int(tmdb_id, 'tmdb_id')

    from media.models import Season
    seasons = list(
        Season.objects.filter(show__tmdb_id=tmdb_id, season_number__gt=0).select_related('show').order_by('season_number')
    )
    if not seasons:
        return Response({'detail': 'Show not found.'}, status=status.HTTP_404_NOT_FOUND)

    marked = _bulk_mark_episodes(
        request.user, tmdb_id, [(season.season_number, _season_episode_rows(season)) for season in seasons],
        request.data.get('watched_at'),
    )
    watched_episodes = WatchEntry.objects.filter(
        user=request.user,
        media_type=WatchEntryMediaType.EPISODE,
        tmdb_id=tmdb_id,
    ).values('season_number', 'episode_number', 'watched_at')

    return Response({'marked': marked, 'episodes': list(watched_episodes)})


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

"""Shared parsing and TMDB-metadata helpers for import providers and engine.

Lives at the app level (not under tasks/) so both the celery layer and the
import engine can use it without circular imports."""

import logging
from datetime import datetime

from django.utils import timezone
from media.models import Movie, Season, TVShow
from media.tmdb import tmdb

from .choices import MediaType, WatchEntryMediaType

logger = logging.getLogger(__name__)


def _safe_int(value):
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_watched_at(value: str | None):
    if not value:
        return None
    normalized = f'{value[:-1]}+00:00' if value.endswith('Z') else value
    try:
        dt = datetime.fromisoformat(normalized)
    except Exception:
        return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _ensure_tv_season_metadata(tmdb_id: int, season_number: int | None, state: dict):
    if season_number is None:
        return
    season_key = (tmdb_id, season_number)
    if season_key in state['season_checked']:
        return

    show = TVShow.objects.filter(tmdb_id=tmdb_id).first()
    if not show:
        state['metadata_errors'] += 1
        state['season_checked'].add(season_key)
        return

    if Season.objects.filter(show=show, season_number=season_number).exists():
        state['metadata_hits'] += 1
        state['season_checked'].add(season_key)
        return

    try:
        tmdb.sync_season(show, season_number, sync_episode_credits=False)
        state['metadata_fetches'] += 1
    except Exception as exc:
        state['metadata_errors'] += 1
        logger.warning('Failed season metadata sync for tv %s season %s: %s', tmdb_id, season_number, exc)
    state['season_checked'].add(season_key)


def _ensure_tmdb_metadata(media_type: str, tmdb_id: int | None) -> bool:
    if not tmdb_id:
        return False

    try:
        if media_type == MediaType.MOVIE:
            tmdb.sync_movie(int(tmdb_id))
        elif media_type in (MediaType.TV, WatchEntryMediaType.EPISODE):
            # Episode credits are display-only and have their own sync task;
            # imports skip them to keep the request count per show minimal.
            tmdb.sync_tv_show(int(tmdb_id), sync_credits=False)
        else:
            return False
        return True
    except Exception as exc:
        logger.warning('Failed metadata sync for %s %s: %s', media_type, tmdb_id, exc)
        return False


def _has_tmdb_metadata(media_type: str, tmdb_id: int | None) -> bool:
    if not tmdb_id:
        return False
    if media_type == MediaType.MOVIE:
        return Movie.objects.filter(tmdb_id=int(tmdb_id)).exists()
    if media_type in (MediaType.TV, WatchEntryMediaType.EPISODE):
        return TVShow.objects.filter(tmdb_id=int(tmdb_id)).exists()
    return False


def _ensure_tmdb_metadata_for_import_item(media_type: str, tmdb_id: int | None, state: dict, season_number: int | None = None):
    if not tmdb_id:
        return

    key_media_type = MediaType.TV if media_type in (MediaType.TV, WatchEntryMediaType.EPISODE) else media_type
    key = (key_media_type, tmdb_id)
    if key not in state['metadata_checked']:
        if _has_tmdb_metadata(media_type, tmdb_id):
            state['metadata_hits'] += 1
        else:
            if _ensure_tmdb_metadata(media_type, tmdb_id):
                state['metadata_fetches'] += 1
            else:
                state['metadata_errors'] += 1
        state['metadata_checked'].add(key)

    if media_type == WatchEntryMediaType.EPISODE:
        _ensure_tv_season_metadata(tmdb_id, season_number, state)


def new_metadata_state() -> dict:
    return {
        'metadata_checked': set(),
        'season_checked': set(),
        'metadata_hits': 0,
        'metadata_fetches': 0,
        'metadata_errors': 0,
    }

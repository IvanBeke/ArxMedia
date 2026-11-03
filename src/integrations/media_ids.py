import logging

import requests

from media.models import TVShow
from media.tmdb import TMDBNotFoundError, tmdb

from .clients import IntegrationError

logger = logging.getLogger(__name__)


def tvdb_id_for_show(tmdb_id: int) -> int:
    """TheTVDB id of a show, from the stored external ids or else TMDB."""
    show = TVShow.objects.filter(tmdb_id=tmdb_id).only('external_ids').first()
    tvdb_id = (show.external_ids if show else {}).get('tvdb_id') or _live_tvdb_id(tmdb_id)
    if not tvdb_id:
        raise IntegrationError('This show has no TheTVDB id, which Sonarr needs.', 422)
    return int(tvdb_id)


def _live_tvdb_id(tmdb_id: int):
    try:
        external_ids = tmdb.get_tv_details(tmdb_id).get('external_ids')
    except (requests.RequestException, TMDBNotFoundError, RuntimeError) as exc:
        logger.warning('Failed to fetch external ids for show %s from TMDB: %s', tmdb_id, exc)
        raise IntegrationError('Could not look up the TheTVDB id for this show.') from exc
    return (external_ids or {}).get('tvdb_id')

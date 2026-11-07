import logging
from collections.abc import Iterable
from functools import partial

from django.db.models import Q

from .http import run_parallel
from .models import Episode
from .tmdb import EXTERNAL_ID_KEYS, tmdb

logger = logging.getLogger(__name__)

EpisodeRef = tuple[int, int, int]


def resolve_episode_external_ids(refs: Iterable[EpisodeRef], *, required: tuple[str, ...], use_cache: bool = True) -> dict[EpisodeRef, dict]:
    """External ids per (show TMDB id, season, episode), stored ones first and TMDB only for episodes lacking a required key.

    Ids fetched from TMDB are saved on the stored episodes; a failed or empty lookup stores nothing.
    """
    refs = list(dict.fromkeys(refs))
    stored = _stored_episodes(refs)
    ids = {ref: dict(stored[ref].external_ids or {}) if ref in stored else {} for ref in refs}
    missing = [ref for ref in refs if not all(ids[ref].get(key) for key in required)]
    results = run_parallel([partial(tmdb.get_episode_external_ids, *ref, use_cache=use_cache) for ref in missing])
    changed = []
    for ref, result in zip(missing, results, strict=True):
        if not isinstance(result, dict):
            logger.warning('Failed to fetch episode external ids for %s S%sE%s from TMDB: %s', *ref, result)
            continue
        merged = {**ids[ref], **{key: result[key] for key in EXTERNAL_ID_KEYS if result.get(key)}}
        if merged != ids[ref] and ref in stored:
            stored[ref].external_ids = merged
            changed.append(stored[ref])
        ids[ref] = merged
    if changed:
        Episode.objects.bulk_update(changed, ['external_ids'])
    return ids


def _stored_episodes(refs: list[EpisodeRef]) -> dict[EpisodeRef, Episode]:
    if not refs:
        return {}
    lookup = Q()
    for show_id, season, episode in refs:
        lookup |= Q(season__show__tmdb_id=show_id, season__season_number=season, episode_number=episode)
    episodes = Episode.objects.filter(lookup).select_related('season__show')
    return {(ep.season.show.tmdb_id, ep.season.season_number, ep.episode_number): ep for ep in episodes}

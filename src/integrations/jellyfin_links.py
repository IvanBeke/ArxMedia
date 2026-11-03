from collections.abc import Callable
from functools import partial
from typing import Any

from django.core.cache import cache

from media.http import run_parallel

from .clients import JellyfinClient

LIBRARY_TTL = 5 * 60
NO_LINKS: dict[str, str | None] = {'show_url': None, 'season_url': None, 'episode_url': None}


def _cached(key: str, loader: Callable[[], Any]) -> Any:
    value = cache.get(key)
    if value is None:
        value = loader()
        cache.set(key, value, LIBRARY_TTL)
    return value


class JellyfinLinks:
    """Finds the Jellyfin pages of shows, seasons and episodes, caching the library lookups briefly."""

    def __init__(self, client: JellyfinClient):
        self._client = client

    def show_links(self, tmdb_id: int, season_number: int | None = None, episode_number: int | None = None) -> dict:
        series = self._series().get(tmdb_id)
        if not series:
            return dict(NO_LINKS)
        links = {**NO_LINKS, 'show_url': self._client.item_url(series)}
        if season_number is None:
            return links
        links['season_url'] = self._url(self._seasons(series['id']).get(season_number))
        if episode_number is not None:
            links['episode_url'] = self._url(self._episodes(series['id'], season_number).get(episode_number))
        return links

    def movie_url(self, tmdb_id: int) -> str | None:
        return self._url(_cached('jellyfin:movies', self._client.movies_by_tmdb_id).get(tmdb_id))

    def episode_urls(self, refs: list[tuple[int, int, int]]) -> list[str | None]:
        series = self._series()
        wanted = sorted({(series[tmdb_id]['id'], season) for tmdb_id, season, _ in refs if tmdb_id in series})
        results = run_parallel([partial(self._episodes, series_id, season) for series_id, season in wanted])
        episodes = {key: result for key, result in zip(wanted, results, strict=True) if isinstance(result, dict)}
        return [self._episode_url(series, episodes, ref) for ref in refs]

    def _episode_url(self, series: dict, episodes: dict, ref: tuple[int, int, int]) -> str | None:
        tmdb_id, season, episode_number = ref
        if tmdb_id not in series:
            return None
        return self._url(episodes.get((series[tmdb_id]['id'], season), {}).get(episode_number))

    def _url(self, item: dict[str, str] | None) -> str | None:
        return self._client.item_url(item) if item else None

    def _series(self) -> dict[int, dict[str, str]]:
        return _cached('jellyfin:series', self._client.series_by_tmdb_id)

    def _seasons(self, series_id: str) -> dict[int, dict[str, str]]:
        return _cached(f'jellyfin:seasons:{series_id}', partial(self._client.seasons, series_id))

    def _episodes(self, series_id: str, season_number: int) -> dict[int, dict[str, str]]:
        return _cached(f'jellyfin:episodes:{series_id}:{season_number}', partial(self._client.episodes, series_id, season_number))

from collections.abc import Callable
from functools import partial
from typing import Any

from django.core.cache import cache

from media.episode_ids import EpisodeRef, resolve_episode_external_ids
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


class _Episodes:
    """A Jellyfin series' episodes, indexed by their numbering and by their TheTVDB id."""

    def __init__(self, records: list[dict[str, Any]]):
        self.by_number = {(record['season'], record['number']): record for record in records}
        self.by_tvdb_id = {record['tvdb_id']: record for record in records if record['tvdb_id']}


class JellyfinLinks:
    """Finds the Jellyfin pages of shows, seasons and episodes, caching the library lookups briefly.

    Jellyfin usually numbers episodes like TheTVDB while we number them like TMDB, so an episode
    without the same season and episode number is matched by its TheTVDB id instead.
    """

    def __init__(self, client: JellyfinClient):
        self._client = client

    def show_links(self, tmdb_id: int, season_number: int | None = None, episode_number: int | None = None) -> dict:
        series = self._series().get(tmdb_id)
        if not series:
            return dict(NO_LINKS)
        links = {**NO_LINKS, 'show_url': self._client.item_url(series)}
        if season_number is None:
            return links
        if episode_number is None:
            season = self._seasons(series['id']).get(season_number)
            if season is None:
                found = self._match_one(series, tmdb_id, season_number, 1)
                season = found and found['season_ref']
        else:
            found = self._match_one(series, tmdb_id, season_number, episode_number)
            links['episode_url'] = self._url(found and found['ref'])
            season = (found and found['season_ref']) or self._seasons(series['id']).get(season_number)
        links['season_url'] = self._url(season)
        return links

    def movie_url(self, tmdb_id: int) -> str | None:
        return self._url(_cached('jellyfin:movies', self._client.movies_by_tmdb_id).get(tmdb_id))

    def episode_urls(self, refs: list[EpisodeRef]) -> list[str | None]:
        series = self._series()
        series_ids = sorted({series[tmdb_id]['id'] for tmdb_id, _, _ in refs if tmdb_id in series})
        results = run_parallel([partial(self._episodes, series_id) for series_id in series_ids])
        libraries = {series_id: result for series_id, result in zip(series_ids, results, strict=True) if isinstance(result, _Episodes)}
        return [self._url(match and match['ref']) for match in self._match(refs, series, libraries)]

    def _match_one(self, series: dict[str, str], tmdb_id: int, season: int, episode: int) -> dict | None:
        return self._match([(tmdb_id, season, episode)], {tmdb_id: series}, {series['id']: self._episodes(series['id'])})[0]

    def _match(self, refs: list[EpisodeRef], series: dict[int, dict[str, str]], libraries: dict[str, _Episodes]) -> list[dict | None]:
        """The Jellyfin episode of each ref: the one with the same numbering, else the one with the same TheTVDB id."""
        searchable = {ref: libraries[series[ref[0]]['id']] for ref in refs if ref[0] in series and series[ref[0]]['id'] in libraries}
        matches = {ref: library.by_number.get(ref[1:]) for ref, library in searchable.items()}
        missed = [ref for ref, match in matches.items() if match is None]
        if missed:
            ids = resolve_episode_external_ids(missed, required=('tvdb_id',), use_cache=False)
            for ref in missed:
                tvdb_id = ids[ref].get('tvdb_id')
                matches[ref] = searchable[ref].by_tvdb_id.get(int(tvdb_id)) if tvdb_id else None
        return [matches.get(ref) for ref in refs]

    def _url(self, item: dict[str, str] | None) -> str | None:
        return self._client.item_url(item) if item else None

    def _series(self) -> dict[int, dict[str, str]]:
        return _cached('jellyfin:series', self._client.series_by_tmdb_id)

    def _seasons(self, series_id: str) -> dict[int, dict[str, str]]:
        return _cached(f'jellyfin:seasons:{series_id}', partial(self._client.seasons, series_id))

    def _episodes(self, series_id: str) -> _Episodes:
        return _Episodes(_cached(f'jellyfin:episodes:{series_id}', partial(self._client.episodes, series_id)))

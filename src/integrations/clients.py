import logging
from typing import Any

import requests
from django.conf import settings

from media.http import build_session

logger = logging.getLogger(__name__)


class IntegrationError(Exception):
    """A failure talking to an external service, carrying the HTTP status to answer with."""

    def __init__(self, detail: str, status_code: int = 502):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _error_detail(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return ''
    if isinstance(payload, dict):
        return str(payload.get('message') or payload.get('errorMessage') or '')
    if isinstance(payload, list):
        return ' '.join(str(item['errorMessage']) for item in payload if isinstance(item, dict) and item.get('errorMessage'))
    return ''


class ArrClient:
    """Transport for the Sonarr/Radarr v3 REST API: authentication, errors and the shared options lookup."""

    SERVICE_NAME = ''
    API_PREFIX = '/api/v3'
    REQUEST_TIMEOUT = 15

    def __init__(self, base_url: str, api_key: str, verify_ssl: bool = True, public_url: str = ''):
        self._base_url = base_url.rstrip('/')
        self._public_url = (public_url or base_url).rstrip('/')
        self._session = build_session(pool_size=2)
        self._session.headers['X-Api-Key'] = api_key
        self._session.verify = verify_ssl

    def _request(self, method: str, path: str, **kwargs) -> Any:
        url = f'{self._base_url}{self.API_PREFIX}{path}'
        try:
            response = self._session.request(method, url, timeout=self.REQUEST_TIMEOUT, **kwargs)
        except requests.RequestException as exc:
            logger.warning('%s request failed for %s: %s', self.SERVICE_NAME, path, exc)
            raise IntegrationError(f'Could not reach {self.SERVICE_NAME}.') from exc
        if response.status_code >= 400:
            raise self._error_for(response)
        return response.json() if response.content else None

    def _error_for(self, response: requests.Response) -> IntegrationError:
        status = response.status_code
        logger.warning('%s responded with HTTP %s: %s', self.SERVICE_NAME, status, response.text[:200])
        if status in (401, 403):
            return IntegrationError(f'{self.SERVICE_NAME} rejected the API key.')
        if status in (400, 404):
            detail = _error_detail(response) or f'{self.SERVICE_NAME} could not process the request.'
            return IntegrationError(detail, status)
        return IntegrationError(f'{self.SERVICE_NAME} responded with an error (HTTP {status}).')

    def options(self) -> dict[str, list[dict[str, Any]]]:
        root_folders = self._request('GET', '/rootfolder')
        quality_profiles = self._request('GET', '/qualityprofile')
        tags = self._request('GET', '/tag')
        return {
            'root_folders': [{'path': folder['path'], 'free_space': folder.get('freeSpace')} for folder in root_folders],
            'quality_profiles': [{'id': profile['id'], 'name': profile['name']} for profile in quality_profiles],
            'tags': [{'id': tag['id'], 'label': tag['label']} for tag in tags],
        }


class RadarrClient(ArrClient):
    SERVICE_NAME = 'Radarr'

    def find_movie(self, tmdb_id: int) -> dict[str, Any] | None:
        movies = self._request('GET', '/movie', params={'tmdbId': tmdb_id})
        return movies[0] if movies else None

    def add_movie(self, tmdb_id: int, data: dict[str, Any]) -> dict[str, Any]:
        lookup = self._request('GET', '/movie/lookup/tmdb', params={'tmdbId': tmdb_id})
        if isinstance(lookup, list):
            lookup = lookup[0] if lookup else None
        if not isinstance(lookup, dict) or not lookup.get('tmdbId'):
            raise IntegrationError('Movie not found in Radarr.', 404)
        payload = {
            **lookup,
            'qualityProfileId': data['quality_profile_id'],
            'rootFolderPath': data['root_folder_path'],
            'minimumAvailability': data['minimum_availability'],
            'monitored': data['monitored'],
            'tags': data['tags'],
            'addOptions': {'searchForMovie': data['search_for_movie']},
        }
        payload.pop('id', None)
        return self._request('POST', '/movie', json=payload)

    def remove_movie(self, radarr_id: int, data: dict[str, Any]) -> None:
        params = {
            'deleteFiles': str(data['delete_files']).lower(),
            'addImportExclusion': str(data['add_import_exclusion']).lower(),
        }
        self._request('DELETE', f'/movie/{radarr_id}', params=params)

    def movie_state(self, movie: dict[str, Any] | None) -> dict[str, Any]:
        if not movie:
            return {'added': False}
        slug = movie.get('titleSlug') or movie.get('tmdbId')
        return {
            'added': True,
            'path': movie.get('path', ''),
            'monitored': bool(movie.get('monitored')),
            'url': f'{self._public_url}/movie/{slug}',
        }


class SonarrClient(ArrClient):
    SERVICE_NAME = 'Sonarr'

    def find_series(self, tvdb_id: int) -> dict[str, Any] | None:
        series = self._request('GET', '/series', params={'tvdbId': tvdb_id})
        return series[0] if series else None

    def add_series(self, tvdb_id: int, data: dict[str, Any]) -> dict[str, Any]:
        results = self._request('GET', '/series/lookup', params={'term': f'tvdb:{tvdb_id}'})
        lookup = next((result for result in results or [] if result.get('tvdbId') == tvdb_id), None)
        if not lookup:
            raise IntegrationError('Series not found in Sonarr.', 404)
        payload = {
            **lookup,
            'qualityProfileId': data['quality_profile_id'],
            'rootFolderPath': data['root_folder_path'],
            'seriesType': data['series_type'],
            'seasonFolder': data['season_folder'],
            'monitored': data['monitored'],
            'tags': data['tags'],
            'addOptions': {
                'monitor': data['monitor'],
                'searchForMissingEpisodes': data['search_for_missing_episodes'],
            },
        }
        payload.pop('id', None)
        return self._request('POST', '/series', json=payload)

    def remove_series(self, sonarr_id: int, data: dict[str, Any]) -> None:
        params = {
            'deleteFiles': str(data['delete_files']).lower(),
            'addImportListExclusion': str(data['add_import_exclusion']).lower(),
        }
        self._request('DELETE', f'/series/{sonarr_id}', params=params)

    def series_state(self, series: dict[str, Any] | None) -> dict[str, Any]:
        if not series:
            return {'added': False}
        slug = series.get('titleSlug') or series.get('tvdbId')
        return {
            'added': True,
            'path': series.get('path', ''),
            'monitored': bool(series.get('monitored')),
            'url': f'{self._public_url}/series/{slug}',
        }


def radarr_credentials() -> tuple[str, str]:
    return getattr(settings, 'RADARR_URL', ''), getattr(settings, 'RADARR_API_KEY', '')


def radarr_client() -> RadarrClient:
    url, api_key = radarr_credentials()
    if not (url and api_key):
        raise IntegrationError('Radarr is not configured.', 503)
    return RadarrClient(
        url, api_key, getattr(settings, 'RADARR_VERIFY_SSL', True), getattr(settings, 'RADARR_PUBLIC_URL', ''),
    )


def sonarr_credentials() -> tuple[str, str]:
    return getattr(settings, 'SONARR_URL', ''), getattr(settings, 'SONARR_API_KEY', '')


def sonarr_client() -> SonarrClient:
    url, api_key = sonarr_credentials()
    if not (url and api_key):
        raise IntegrationError('Sonarr is not configured.', 503)
    return SonarrClient(
        url, api_key, getattr(settings, 'SONARR_VERIFY_SSL', True), getattr(settings, 'SONARR_PUBLIC_URL', ''),
    )

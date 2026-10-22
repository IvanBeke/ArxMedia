import logging
from datetime import datetime

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .http import build_session, response_cache_key

logger = logging.getLogger(__name__)


class TVMazeError(requests.RequestException):
    """Base class for TVMaze failures that callers should handle like request errors."""


class TVMazeNotFound(TVMazeError):
    """TVMaze returned a definitive 404 for this lookup."""


class TVMazeUnavailable(TVMazeError):
    """TVMaze timed out or was unreachable; further calls should be skipped briefly."""


class TVMazeService:
    BASE_URL = getattr(settings, 'TVMAZE_BASE_URL', 'https://api.tvmaze.com')
    CACHE_TTL = 86400
    MISSING_TTL = 86400
    UNAVAILABLE_TTL = 60
    REQUEST_TIMEOUT = 20
    UNAVAILABLE_CACHE_KEY = 'tvmaze:unavailable'
    _MISSING = '__tvmaze_missing__'
    _UNAVAILABLE = '__tvmaze_unavailable__'

    def __init__(self):
        self._session = build_session()

    def _request(self, path, params=None):
        params = params or {}
        cache_key = response_cache_key('tvmaze', path, params)
        self._raise_for_cached_marker(cache_key, path)
        if (cached := cache.get(cache_key)) is not None:
            return cached
        self._raise_unavailable_short_circuit(path)

        return self._fetch_and_cache(path, params, cache_key)

    def _raise_for_cached_marker(self, cache_key, path):
        cached = cache.get(cache_key)
        if cached == self._MISSING:
            raise TVMazeNotFound(f'TVMaze resource not found: {path}')
        if cached == self._UNAVAILABLE:
            raise TVMazeUnavailable(f'TVMaze unavailable: {path}')

    def _raise_unavailable_short_circuit(self, path):
        if cache.get(self.UNAVAILABLE_CACHE_KEY):
            raise TVMazeUnavailable(f'TVMaze temporarily unavailable before requesting {path}')

    def _fetch_and_cache(self, path, params, cache_key):
        response = self._get_response(path, params, cache_key)
        if response.status_code == 404:
            cache.set(cache_key, self._MISSING, self.MISSING_TTL)
            raise TVMazeNotFound(f'TVMaze resource not found: {path}')

        response.raise_for_status()
        data = response.json()
        cache.set(cache_key, data, self.CACHE_TTL)
        return data

    def _get_response(self, path, params, cache_key):
        url = f'{self.BASE_URL}{path}'
        try:
            return self._session.get(url, params=params, timeout=self.REQUEST_TIMEOUT)
        except (requests.Timeout, requests.ConnectionError) as exc:
            cache.set(cache_key, self._UNAVAILABLE, self.UNAVAILABLE_TTL)
            cache.set(self.UNAVAILABLE_CACHE_KEY, True, self.UNAVAILABLE_TTL)
            raise TVMazeUnavailable(f'TVMaze request failed for {path}: {exc}') from exc

    def lookup_show_by_id(self, tvmaze_id):
        try:
            show = self._request(f'/shows/{tvmaze_id}')
        except requests.RequestException as exc:
            logger.warning('TVMaze show lookup failed for %s: %s', tvmaze_id, exc)
            return None
        return show if isinstance(show, dict) else None

    def lookup_show(self, external_ids=None, show_name=None, year=None):
        show = self._lookup_by_external_ids(external_ids or {})
        if show:
            return show
        return self._lookup_by_name(show_name, year)

    def _lookup_by_external_ids(self, external_ids):
        lookup_sources = (
            ('tvdb_id', 'thetvdb'),
            ('imdb_id', 'imdb'),
            ('tvrage_id', 'tvrage'),
        )
        for source, parameter in lookup_sources:
            external_id = external_ids.get(source)
            if not external_id:
                continue
            try:
                show = self._lookup_show_by_source(source, external_id, parameter)
            except TVMazeUnavailable:
                return None
            if show:
                return show
        return None

    def _lookup_show_by_source(self, source, external_id, parameter):
        try:
            show = self._request('/lookup/shows', {parameter: external_id})
        except TVMazeUnavailable as exc:
            logger.warning('TVMaze %s lookup unavailable for %s: %s', source, external_id, exc)
            raise
        except requests.RequestException as exc:
            logger.warning('TVMaze %s lookup failed for %s: %s', source, external_id, exc)
            return None
        return show if isinstance(show, dict) and show.get('id') else None

    def _lookup_by_name(self, show_name, year):
        if not show_name:
            return None
        results = self._search_shows(show_name)
        for result in results or []:
            show = self._search_result_show(result, year)
            if show:
                return show
        return None

    def _search_shows(self, show_name):
        try:
            return self._request('/search/shows', {'q': show_name})
        except TVMazeUnavailable as exc:
            logger.warning('TVMaze search unavailable for %s: %s', show_name, exc)
            return None
        except requests.RequestException as exc:
            logger.warning('TVMaze search failed for %s: %s', show_name, exc)
            return None

    @staticmethod
    def _search_result_show(result, year):
        show = result.get('show') or result
        if not isinstance(show, dict):
            return None
        premiered = show.get('premiered')
        if year and premiered and premiered[:4] != str(year):
            return None
        return show

    def lookup_season_show(self, external_ids=None, season_name=None, year=None):
        return self.lookup_show(external_ids=external_ids, show_name=season_name, year=year)

    def get_show_episodes(self, tvmaze_id):
        try:
            return self._request(f'/shows/{tvmaze_id}/episodes')
        except requests.RequestException as exc:
            logger.warning('TVMaze episodes fetch failed for %s: %s', tvmaze_id, exc)
            return []

    @staticmethod
    def strip_timezone(value):
        if not value:
            return ''
        return str(value).strip()

    @staticmethod
    def parse_air_datetime(air_date, air_time, timezone_name):
        if not air_date:
            return None
        naive = TVMazeService._parse_local_datetime(air_date, air_time)
        if naive is None:
            return None
        return TVMazeService._make_aware(naive, timezone_name)

    @staticmethod
    def _parse_local_datetime(air_date, air_time):
        try:
            return datetime.fromisoformat(f'{air_date}T{air_time or "00:00:00"}')
        except ValueError:
            return None

    @staticmethod
    def _make_aware(naive, timezone_name):
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(timezone_name)
        except Exception:
            tz = None
        return timezone.make_aware(naive, tz or timezone.get_current_timezone())

    @staticmethod
    def parse_show_schedule_datetime(show, air_date):
        if not isinstance(show, dict):
            return None
        schedule = show.get('schedule') or {}
        air_time = schedule.get('time') or ''
        if not air_time:
            return None
        return TVMazeService.parse_air_datetime(
            air_date,
            air_time,
            TVMazeService.show_timezone(show),
        )

    @staticmethod
    def normalize_episode_from_tvmaze(show, episode):
        if not isinstance(episode, dict):
            return None

        network_tz = TVMazeService.show_timezone(show)
        air_date = episode.get('airdate')
        air_time = episode.get('airtime') or ''
        zone_name = network_tz
        broadcast_start = TVMazeService.parse_air_datetime(air_date, air_time, zone_name)

        return {
            'tmdb_id': None,
            'name': episode.get('name') or '',
            'overview': episode.get('summary') or '',
            'air_date': air_date,
            'broadcast_start': broadcast_start,
            'runtime': episode.get('runtime'),
            'episode_type': '',
        }

    @staticmethod
    def show_timezone(show):
        if not isinstance(show, dict):
            return ''

        network_country = (show.get('network') or {}).get('country') or {}
        web_channel_country = (show.get('webChannel') or {}).get('country') or {}
        return network_country.get('timezone') or web_channel_country.get('timezone') or ''


tvmaze = TVMazeService()

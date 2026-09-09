import json
import logging
from datetime import datetime

import redis
import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class TVMazeService:
    BASE_URL = getattr(settings, 'TVMAZE_BASE_URL', 'https://api.tvmaze.com')
    CACHE_TTL = 86400

    def __init__(self):
        self._session = requests.Session()
        self._redis = None

    def _get_redis(self):
        if self._redis is None:
            url = getattr(settings, 'REDIS_URL', None)
            if url:
                self._redis = redis.from_url(url, decode_responses=True)
        return self._redis

    def _request(self, path, params=None):
        params = params or {}
        cache_key = f'tvmaze:{path}:{json.dumps(params, sort_keys=True)}'
        cache = self._get_redis()
        if cache:
            cached = cache.get(cache_key)
            if cached is not None:
                return json.loads(cached)
        url = f'{self.BASE_URL}{path}'
        response = self._session.get(url, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
        if cache:
            try:
                cache.set(cache_key, json.dumps(data), ex=self.CACHE_TTL)
            except redis.exceptions.ConnectionError as exc:
                logger.warning('TVMaze cache set failed for key %s: %s', cache_key, exc)
        return data

    def lookup_show_by_id(self, tvmaze_id):
        try:
            show = self._request(f'/shows/{tvmaze_id}')
        except requests.RequestException as exc:
            logger.warning('TVMaze show lookup failed for %s: %s', tvmaze_id, exc)
            return None
        return show if isinstance(show, dict) else None

    def lookup_show(self, external_ids=None, show_name=None, year=None):
        external_ids = external_ids or {}
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
                show = self._request('/lookup/shows', {parameter: external_id})
            except requests.RequestException as exc:
                logger.warning('TVMaze %s lookup failed for %s: %s', source, external_id, exc)
                continue
            if isinstance(show, dict) and show.get('id'):
                return show

        if not show_name:
            return None
        try:
            results = self._request('/search/shows', {'q': show_name})
        except requests.RequestException as exc:
            logger.warning('TVMaze search failed for %s: %s', show_name, exc)
            return None

        for result in results:
            show = result.get('show') or result
            if not isinstance(show, dict):
                continue
            if year:
                premiered = show.get('premiered')
                if premiered and premiered[:4] != str(year):
                    continue
            return show
        return None

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
        if air_time:
            try:
                naive = datetime.fromisoformat(f'{air_date}T{air_time}')
            except ValueError:
                return None
        else:
            try:
                naive = datetime.fromisoformat(f'{air_date}T00:00:00')
            except ValueError:
                return None

        if not timezone_name:
            return timezone.make_aware(naive, timezone.get_current_timezone())

        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(timezone_name)
        except Exception:
            return timezone.make_aware(naive, timezone.get_current_timezone())

        return timezone.make_aware(naive, tz)

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

import json
import logging
import time

import redis
import requests
from django.conf import settings
from django.utils.dateparse import parse_date

from .models import Episode, EpisodeCredit, Genre, Movie, Season, TVShow
from .tvmaze import tvmaze

logger = logging.getLogger(__name__)


class TMDBNotFoundError(Exception):
    pass


def _split_bundled_seasons(season_numbers: list[int], bundled_limit: int) -> tuple[list[int], list[int]]:
    """Split seasons into those fetchable via append_to_response and leftovers."""
    bundled = season_numbers[:bundled_limit]
    remaining = season_numbers[bundled_limit:]
    return bundled, remaining


def _non_empty_defaults(defaults):
    """Drop null/empty values so upstream removals never clear stored fields."""
    return {
        key: value
        for key, value in defaults.items()
        if not (value is None or value == '' or (isinstance(value, list) and not value))
    }


EXTERNAL_ID_KEYS = ('tvdb_id', 'imdb_id', 'tvrage_id')


def _external_ids(data):
    source = data.get('external_ids') or {}
    return {
        key: source[key]
        for key in EXTERNAL_ID_KEYS
        if source.get(key)
    }


class TMDBService:
    BASE_URL = getattr(settings, 'TMDB_BASE_URL', 'https://api.themoviedb.org/3')
    API_KEY = getattr(settings, 'TMDB_API_KEY', '')
    CACHE_TTL = 604800  # 7 days
    REQUEST_RETRIES = 5
    APPEND_SEASON_LIMIT = 20  # TMDB caps append_to_response sub-requests
    EXTERNAL_ID_APPEND_COUNT = 1
    BUNDLED_SEASON_LIMIT = APPEND_SEASON_LIMIT - EXTERNAL_ID_APPEND_COUNT

    def __init__(self):
        self._redis = None

    def _get_redis(self):
        if self._redis is None:
            url = getattr(settings, 'REDIS_URL', None)
            if url:
                self._redis = redis.from_url(url, decode_responses=True)
        return self._redis

    def _should_retry_request(self, exc, endpoint: str) -> bool:
        if not isinstance(exc, requests.HTTPError):
            return True

        response = exc.response
        status_code = response.status_code if response is not None else None
        if status_code == 404:
            raise TMDBNotFoundError(f'TMDB resource not found for endpoint {endpoint}') from exc
        return status_code is None or status_code == 429 or status_code >= 500

    def _get(self, endpoint, params=None, *, use_cache=True):
        if params is None:
            params = {}

        cache_key = f'tmdb:{endpoint}:{json.dumps(params, sort_keys=True)}'
        r = self._get_redis()

        if r and use_cache:
            cached = r.get(cache_key)
            if cached is not None:
                return json.loads(cached)

        params['api_key'] = self.API_KEY

        response_data = None
        for attempt in range(self.REQUEST_RETRIES + 1):
            try:
                response = requests.get(f'{self.BASE_URL}{endpoint}', params=params)
                response.raise_for_status()
                response_data = response.json()
                break
            except requests.RequestException as exc:
                should_retry = self._should_retry_request(exc, endpoint)
                if not should_retry or attempt >= self.REQUEST_RETRIES:
                    raise
                time.sleep(min(30, 2**attempt))

        if response_data is None:
            raise RuntimeError(f'TMDB request failed without response payload for endpoint {endpoint}')

        data = response_data

        if r:
            try:
                r.set(cache_key, json.dumps(data), ex=self.CACHE_TTL)
            except redis.exceptions.ConnectionError as exc:
                logger.warning('Redis cache set failed for key %s: %s', cache_key, exc)

        return data

    def search_multi(self, query, page=1):
        return self._get('/search/multi', {'query': query, 'page': page})

    def search_movies(self, query, page=1):
        return self._get('/search/movie', {'query': query, 'page': page})

    def search_tv(self, query, page=1):
        return self._get('/search/tv', {'query': query, 'page': page})

    def find_by_external_id(self, external_id, external_source):
        return self._get(f'/find/{external_id}', {'external_source': external_source})

    def get_movie(self, tmdb_id, *, use_cache=True):
        return self._get(f'/movie/{tmdb_id}', use_cache=use_cache)

    def get_movie_credits(self, tmdb_id):
        return self._get(f'/movie/{tmdb_id}/credits')

    def get_tv_show(self, tmdb_id, *, use_cache=True):
        return self._get(f'/tv/{tmdb_id}', use_cache=use_cache)

    def get_tv_show_with_seasons(self, tmdb_id, season_numbers, *, use_cache=True):
        """Fetch a show plus up to APPEND_SEASON_LIMIT seasons (episodes
        included) in a single TMDB request via ``append_to_response``."""
        appends = ['external_ids'] + [f'season/{number}' for number in season_numbers[:self.BUNDLED_SEASON_LIMIT]]
        params = {}
        if appends:
            params['append_to_response'] = ','.join(appends)
        return self._get(f'/tv/{tmdb_id}', params or None, use_cache=use_cache)

    def get_tv_aggregate_credits(self, tmdb_id):
        return self._get(f'/tv/{tmdb_id}/aggregate_credits')

    def get_movie_watch_providers(self, tmdb_id):
        return self._get(f'/movie/{tmdb_id}/watch/providers')

    def get_tv_watch_providers(self, tmdb_id):
        return self._get(f'/tv/{tmdb_id}/watch/providers')

    def get_season(self, show_id, season_number, *, use_cache=True):
        return self._get(
            f'/tv/{show_id}/season/{season_number}',
            {'append_to_response': 'credits,external_ids'},
            use_cache=use_cache,
        )

    def get_season_external_ids(self, show_id, season_number, *, use_cache=True):
        return self._get(f'/tv/{show_id}/season/{season_number}/external_ids', use_cache=use_cache)

    def get_episode_credits(self, show_id, season_number, episode_number, *, use_cache=True):
        return self._get(
            f'/tv/{show_id}/season/{season_number}/episode/{episode_number}/credits',
            use_cache=use_cache,
        )

    def get_trending(self, media_type='all', time_window='week'):
        return self._get(f'/trending/{media_type}/{time_window}')

    def get_popular_movies(self, page=1):
        return self._get('/movie/popular', {'page': page})

    def get_popular_tv(self, page=1):
        return self._get('/tv/popular', {'page': page})

    def get_top_rated_movies(self, page=1):
        return self._get('/movie/top_rated', {'page': page})

    def get_top_rated_tv(self, page=1):
        return self._get('/tv/top_rated', {'page': page})

    def get_movie_changes(self, start_date: str, end_date: str, page: int = 1, *, use_cache: bool = False):
        return self._get(
            '/movie/changes',
            {'start_date': start_date, 'end_date': end_date, 'page': page},
            use_cache=use_cache,
        )

    def get_tv_changes(self, start_date: str, end_date: str, page: int = 1, *, use_cache: bool = False):
        return self._get(
            '/tv/changes',
            {'start_date': start_date, 'end_date': end_date, 'page': page},
            use_cache=use_cache,
        )

    def sync_movie(self, tmdb_id, *, use_cache=True):
        """Fetch movie from TMDB and save/update locally."""
        data = self.get_movie(tmdb_id, use_cache=use_cache)
        movie_defaults = {
            'title': data.get('title', ''),
            'overview': data.get('overview', ''),
            'poster_path': data.get('poster_path', '') or '',
            'backdrop_path': data.get('backdrop_path', '') or '',
            'release_date': parse_date(data['release_date']) if data.get('release_date') else None,
            'runtime': data.get('runtime'),
            'vote_average': data.get('vote_average', 0),
            'vote_count': data.get('vote_count', 0),
            'language': data.get('original_language', ''),
            'tagline': data.get('tagline', ''),
            'status': data.get('status', ''),
        }
        movie, _ = Movie.objects.update_or_create(
            tmdb_id=tmdb_id,
            defaults=_non_empty_defaults(movie_defaults),
            create_defaults=movie_defaults,
        )
        for g in data.get('genres', []):
            genre, _ = Genre.objects.get_or_create(tmdb_id=g['id'], defaults={'name': g['name']})
            movie.genres.add(genre)
        return movie

    def sync_tv_show(self, tmdb_id, user_id=None, sync_credits: bool = True, *, recompute_user_statuses: bool = True, use_cache: bool = True):
        """Fetch TV show from TMDB and save/update locally, including all seasons and episodes."""
        data = self.get_tv_show(tmdb_id, use_cache=use_cache)
        season_numbers = self._season_numbers(data)
        data = self.get_tv_show_with_seasons(tmdb_id, season_numbers, use_cache=use_cache)
        show = self._upsert_show(tmdb_id, data)
        tvmaze_show, _ = self._resolve_tvmaze(show, include_episodes=False)
        self._apply_tvmaze_metadata(show, tvmaze_show)
        tvmaze_context: dict[int, tuple[dict | None, list[dict]]] = {}
        self._sync_show_genres(show, data)
        self._sync_show_seasons(show, season_numbers, data, sync_credits, use_cache, tvmaze_context)

        if recompute_user_statuses:
            try:
                from tracking.status_sync import refresh_all_statuses_for_show

                refresh_all_statuses_for_show(int(tmdb_id), current_user_id=user_id)
            except Exception as exc:
                logger.warning('Failed to refresh statuses for tv %s: %s', tmdb_id, exc)

        return show

    @staticmethod
    def _season_numbers(data):
        season_numbers = [
            int(season['season_number'])
            for season in data.get('seasons', [])
            if isinstance(season.get('season_number'), int)
        ]
        if not season_numbers:
            season_numbers = list(range(1, int(data.get('number_of_seasons') or 0) + 1))
        return season_numbers

    def _upsert_show(self, tmdb_id, data):
        existing_show = TVShow.objects.filter(tmdb_id=tmdb_id).first()
        external_ids = dict(existing_show.external_ids or {}) if existing_show else {}
        external_ids.update(_external_ids(data))
        runtimes = data.get('episode_run_time') or []
        episode_runtime = next((r for r in runtimes if isinstance(r, int) and r > 0), None)
        defaults = {
            'name': data.get('name', ''), 'overview': data.get('overview', ''),
            'poster_path': data.get('poster_path', '') or '', 'backdrop_path': data.get('backdrop_path', '') or '',
            'first_air_date': parse_date(data['first_air_date']) if data.get('first_air_date') else None,
            'last_air_date': parse_date(data['last_air_date']) if data.get('last_air_date') else None,
            'number_of_seasons': data.get('number_of_seasons', 0), 'number_of_episodes': data.get('number_of_episodes', 0),
            'vote_average': data.get('vote_average', 0), 'vote_count': data.get('vote_count', 0),
            'language': data.get('original_language', ''), 'status': data.get('status', ''),
            'networks': ', '.join(n['name'] for n in data.get('networks', [])),
            'external_ids': external_ids, 'episode_runtime': episode_runtime,
        }
        show, _ = TVShow.objects.update_or_create(
            tmdb_id=tmdb_id, defaults=_non_empty_defaults(defaults), create_defaults=defaults
        )
        return show

    @staticmethod
    def _sync_show_genres(show, data):
        for genre_data in data.get('genres', []):
            genre, _ = Genre.objects.get_or_create(tmdb_id=genre_data['id'], defaults={'name': genre_data['name']})
            show.genres.add(genre)

    def _sync_show_seasons(self, show, season_numbers, data, sync_credits, use_cache, tvmaze_context):
        bundled, remaining = _split_bundled_seasons(season_numbers, self.BUNDLED_SEASON_LIMIT)
        for season_number in bundled:
            season_data = data.get(f'season/{season_number}')
            if not isinstance(season_data, dict) or not season_data:
                remaining.append(season_number)
                continue
            self._sync_season_payload(show, season_number, season_data, sync_credits, use_cache, tvmaze_context)
        for season_number in remaining:
            self._sync_season_payload(show, season_number, None, sync_credits, use_cache, tvmaze_context)

    def _sync_season_payload(self, show, season_number, data, sync_credits, use_cache, tvmaze_context):
        try:
            if data is None:
                return self.sync_season(show, season_number, sync_episode_credits=sync_credits, use_cache=use_cache, tvmaze_context=tvmaze_context)
            return self._upsert_season(show, season_number, data, sync_episode_credits=sync_credits, use_cache=use_cache, tvmaze_context=tvmaze_context)
        except Exception as exc:
            logger.warning('Failed to sync season %s for tv %s: %s', season_number, show.tmdb_id, exc)

    def sync_season(self, show, season_number, sync_episode_credits: bool = True, *, use_cache: bool = True, tvmaze_context=None):
        """Fetch a season from TMDB and save/update locally with all episodes."""
        return self._sync_season(
            show,
            season_number,
            sync_episode_credits=sync_episode_credits,
            use_cache=use_cache,
            tvmaze_context=tvmaze_context,
        )

    def _sync_season(self, show, season_number, *, sync_episode_credits=True, use_cache=True, tvmaze_context=None):
        data = self.get_season(show.tmdb_id, season_number, use_cache=use_cache)
        return self._upsert_season(
            show,
            season_number,
            data,
            sync_episode_credits=sync_episode_credits,
            use_cache=use_cache,
            tvmaze_context=tvmaze_context,
        )

    def _resolve_tvmaze(self, show, *, include_episodes=True):
        external_ids = dict(show.external_ids or {})
        try:
            tvmaze_show = None
            if external_ids.get('tvmaze_id'):
                tvmaze_show = tvmaze.lookup_show_by_id(external_ids['tvmaze_id'])
            if not tvmaze_show:
                tvmaze_show = tvmaze.lookup_show(
                    external_ids=external_ids,
                    show_name=show.name,
                    year=show.first_air_date.year if show.first_air_date else None,
                )
            episodes = tvmaze.get_show_episodes(tvmaze_show['id']) if include_episodes and tvmaze_show and tvmaze_show.get('id') else []
            if tvmaze_show and tvmaze_show.get('id'):
                external_ids['tvmaze_id'] = int(tvmaze_show['id'])
            return tvmaze_show, episodes
        except Exception as exc:
            logger.warning('Failed to resolve TVMaze metadata for tv %s: %s', show.tmdb_id, exc)
            return None, []

    def _apply_tvmaze_metadata(self, show, tvmaze_show):
        if not tvmaze_show or not tvmaze_show.get('id'):
            return
        external_ids = dict(show.external_ids or {})
        external_ids['tvmaze_id'] = int(tvmaze_show['id'])
        show.external_ids = external_ids
        if not show.episode_runtime:
            show.episode_runtime = tvmaze_show.get('runtime') or tvmaze_show.get('averageRuntime')
        show.save(update_fields=['external_ids', 'episode_runtime', 'updated_at'])

    def _upsert_season(self, show, season_number: int, data: dict, sync_episode_credits: bool = True, *, use_cache: bool = True, tvmaze_context=None, tvmaze_show=None, tvmaze_episodes=None):
        """Persist one season (with episodes) from a TMDB season payload."""
        season = self._upsert_season_record(show, season_number, data, use_cache)
        tvmaze_show, tvmaze_episodes = self._season_tvmaze_context(show, season, tvmaze_context, tvmaze_show, tvmaze_episodes)
        episodes_by_number = {(e.get('season'), e.get('number')): e for e in tvmaze_episodes or []}
        episodes_by_name_date = {
            (self._normalize_title(e.get('name')), e.get('airdate')): e
            for e in tvmaze_episodes or []
            if e.get('airdate')
        }
        for ep_data in data.get('episodes', []):
            episode_number = ep_data['episode_number']
            episode = self._upsert_episode_record(season, ep_data)
            broadcast_start = None
            remote_ep = episodes_by_number.get((season_number, episode_number))
            if remote_ep is None:
                remote_ep = episodes_by_name_date.get((self._normalize_title(ep_data.get('name')), ep_data.get('air_date')))
            if remote_ep is None and ep_data.get('air_date'):
                candidates = [e for e in tvmaze_episodes or [] if e.get('airdate') == ep_data['air_date']]
                remote_ep = candidates[0] if len(candidates) == 1 else None
            if remote_ep:
                tvmaze_payload = tvmaze.normalize_episode_from_tvmaze(tvmaze_show, remote_ep)
                if tvmaze_payload:
                    episode.external_ids = dict(episode.external_ids or {})
                    episode.external_ids['tvmaze_id'] = remote_ep.get('id')
                    broadcast_start = tvmaze_payload.get('broadcast_start')
                    if not remote_ep.get('airtime'):
                        broadcast_start = tvmaze.parse_show_schedule_datetime(tvmaze_show, ep_data.get('air_date'))
                    episode.runtime = episode.runtime or tvmaze_payload.get('runtime')
            elif tvmaze_show:
                broadcast_start = tvmaze.parse_show_schedule_datetime(tvmaze_show, ep_data.get('air_date'))

            episode.broadcast_start = broadcast_start
            episode.save(update_fields=['external_ids', 'broadcast_start', 'runtime'])

            if sync_episode_credits:
                self._sync_episode_credits_safely(show, season_number, episode_number, use_cache)
        return season

    def _upsert_season_record(self, show, season_number, data, use_cache):
        defaults = {
            'tmdb_id': data.get('id', 0), 'name': data.get('name', ''), 'overview': data.get('overview', ''),
            'poster_path': data.get('poster_path', '') or '',
            'air_date': parse_date(data['air_date']) if data.get('air_date') else None,
            'episode_count': data.get('episode_count', 0), 'external_ids': _external_ids(data),
        }
        season, _ = Season.objects.update_or_create(
            show=show, season_number=season_number,
            defaults=_non_empty_defaults(defaults), create_defaults=defaults,
        )
        if not season.external_ids:
            season.external_ids = _external_ids(data) or _external_ids(
                self.get_season_external_ids(show.tmdb_id, season_number, use_cache=use_cache)
            )
            season.save(update_fields=['external_ids'])
        return season

    @staticmethod
    def _upsert_episode_record(season, data):
        defaults = {
            'tmdb_id': data.get('id', 0), 'name': data.get('name', ''), 'overview': data.get('overview', ''),
            'still_path': data.get('still_path', '') or '',
            'air_date': parse_date(data['air_date']) if data.get('air_date') else None,
            'runtime': data.get('runtime'), 'vote_average': data.get('vote_average', 0),
            'vote_count': data.get('vote_count', 0), 'episode_type': data.get('episode_type', '') or '',
            'external_ids': _external_ids(data),
        }
        episode, _ = Episode.objects.update_or_create(
            season=season, episode_number=data['episode_number'],
            defaults=_non_empty_defaults(defaults), create_defaults=defaults,
        )
        return episode

    def _season_tvmaze_context(self, show, season, context, tvmaze_show, tvmaze_episodes):
        context = context if context is not None else {season.season_number: (tvmaze_show, tvmaze_episodes or [])}
        if season.season_number not in context:
            resolved = self._resolve_tvmaze_season(show, season)
            if resolved is None and show.external_ids.get('tvmaze_id'):
                resolved = tvmaze.lookup_show_by_id(show.external_ids['tvmaze_id'])
            context[season.season_number] = (resolved, tvmaze.get_show_episodes(resolved['id']) if resolved else [])
        resolved, episodes = context[season.season_number]
        if resolved and resolved.get('id'):
            season.external_ids['tvmaze_id'] = int(resolved['id'])
            season.save(update_fields=['external_ids'])
        return resolved, episodes

    def _sync_episode_credits_safely(self, show, season_number, episode_number, use_cache):
        try:
            self.sync_episode_credits(show.tmdb_id, season_number, episode_number, show=show, use_cache=use_cache)
        except Exception as exc:
            logger.warning('Failed to sync episode credits for tv %s season %s episode %s: %s', show.tmdb_id, season_number, episode_number, exc)

    @staticmethod
    def _normalize_title(value):
        return ' '.join(str(value or '').casefold().replace('-', ' ').split())

    def _resolve_tvmaze_season(self, show, season):
        if season.external_ids.get('tvmaze_id'):
            return tvmaze.lookup_show_by_id(season.external_ids['tvmaze_id'])
        return tvmaze.lookup_season_show(
            external_ids=season.external_ids,
            season_name=f'{show.name} {season.name}',
            year=season.air_date.year if season.air_date else None,
        )

    def sync_episode_credits(self, show_id, season_number, episode_number, *, show=None, use_cache: bool = True):
        if show is None:
            show = TVShow.objects.filter(tmdb_id=show_id).first() or self.sync_tv_show(show_id, use_cache=use_cache)

        season = show.seasons.filter(season_number=season_number).first()
        if season is None:
            season = self.sync_season(show, season_number, use_cache=use_cache)

        episode = season.episodes.filter(episode_number=episode_number).first()
        if episode is None:
            season = self.sync_season(show, season_number, use_cache=use_cache)
            episode = season.episodes.get(episode_number=episode_number)

        credits = self.get_episode_credits(show_id, season_number, episode_number, use_cache=use_cache)
        credit_defaults = {
            'cast': credits.get('cast') or [],
            'crew': credits.get('crew') or [],
            'guest_stars': credits.get('guest_stars') or [],
        }
        episode_credit, _ = EpisodeCredit.objects.update_or_create(
            episode=episode,
            defaults=_non_empty_defaults(credit_defaults),
            create_defaults=credit_defaults,
        )
        return episode_credit


tmdb = TMDBService()

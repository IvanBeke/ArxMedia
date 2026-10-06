import logging
import time
from functools import partial

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils.dateparse import parse_date

from .http import build_session, response_cache_key, run_parallel
from .models import Episode, EpisodeCredit, Genre, Movie, Season, TVShow
from .tvmaze import tvmaze

logger = logging.getLogger(__name__)


class TMDBNotFoundError(Exception):
    pass


def _non_empty_defaults(defaults):
    """Drop null/empty values so upstream removals never clear stored fields."""
    return {
        key: value
        for key, value in defaults.items()
        if not (value is None or value == '' or (isinstance(value, list) and not value))
    }


def _parse_date(value):
    return parse_date(value) if value else None


EXTERNAL_ID_KEYS = ('tvdb_id', 'imdb_id', 'tvrage_id')
EPISODE_FIELDS = (
    'tmdb_id', 'name', 'overview', 'still_path', 'air_date', 'runtime', 'vote_average',
    'vote_count', 'episode_type', 'external_ids', 'broadcast_start',
)
CREDIT_FIELDS = ('cast', 'crew', 'guest_stars')


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
    REQUEST_TIMEOUT = (10, 120)  # connect, read (seconds)
    # 5xx responses from TMDB are usually poisoned payloads (e.g. a season
    # whose credits break append_to_response serialization), not transient
    # blips: one retry, then let the caller fall back instead of burning ~32s.
    SERVER_ERROR_RETRIES = 1
    APPEND_LIMIT = 20  # TMDB caps append_to_response sub-requests
    MOVIE_APPENDS = ('keywords', 'external_ids', 'watch/providers')
    TV_APPENDS = ('external_ids', 'watch/providers')
    POSTCREDITS_KEYWORD_IDS = frozenset({179430, 179431})  # after credits stinger, during credits stinger

    def __init__(self):
        self._session = build_session()

    def _should_retry_request(self, exc, endpoint: str) -> bool:
        if isinstance(exc, requests.Timeout):
            return False
        if not isinstance(exc, requests.HTTPError):
            return True

        response = exc.response
        status_code = response.status_code if response is not None else None
        if status_code == 404:
            raise TMDBNotFoundError(f'TMDB resource not found for endpoint {endpoint}') from exc
        return status_code is None or status_code == 429 or status_code >= 500

    @staticmethod
    def _is_server_error(exc) -> bool:
        return (
            isinstance(exc, requests.HTTPError)
            and exc.response is not None
            and exc.response.status_code >= 500
        )

    def _get(self, endpoint, params=None, *, use_cache=True):
        params = dict(params or {})

        cache_key = response_cache_key('tmdb', endpoint, params)
        if use_cache:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached

        params['api_key'] = self.API_KEY

        response_data = None
        for attempt in range(self.REQUEST_RETRIES + 1):
            try:
                response = self._session.get(
                    f'{self.BASE_URL}{endpoint}',
                    params=params,
                    timeout=self.REQUEST_TIMEOUT,
                )
                response.raise_for_status()
                response_data = response.json()
                break
            except requests.RequestException as exc:
                should_retry = self._should_retry_request(exc, endpoint)
                if not should_retry or attempt >= self.REQUEST_RETRIES:
                    raise
                if self._is_server_error(exc) and attempt >= self.SERVER_ERROR_RETRIES:
                    raise
                time.sleep(min(30, 2**attempt))

        if response_data is None:
            raise RuntimeError(f'TMDB request failed without response payload for endpoint {endpoint}')

        cache.set(cache_key, response_data, self.CACHE_TTL)
        return response_data

    def _get_appended(self, endpoint, appends, *, use_cache=True):
        """Fetch ``endpoint`` with ``append_to_response``.

        A poisoned sub-resource makes TMDB answer 500 for the whole request,
        so on server errors the appends are split in halves until the bad one
        is isolated and dropped; every other append still comes through.
        """
        appends = list(appends)
        params = {'append_to_response': ','.join(appends)} if appends else None
        try:
            return self._get(endpoint, params, use_cache=use_cache)
        except requests.HTTPError as exc:
            if not appends or not self._is_server_error(exc):
                raise
        if len(appends) == 1:
            logger.warning('TMDB append %s failed for %s; skipping it', appends[0], endpoint)
            return self._get(endpoint, use_cache=use_cache)
        middle = len(appends) // 2
        return {
            **self._get_appended(endpoint, appends[:middle], use_cache=use_cache),
            **self._get_appended(endpoint, appends[middle:], use_cache=use_cache),
        }

    def search_multi(self, query, page=1):
        return self._get('/search/multi', {'query': query, 'page': page})

    def search_movies(self, query, page=1):
        return self._get('/search/movie', {'query': query, 'page': page})

    def search_tv(self, query, page=1):
        return self._get('/search/tv', {'query': query, 'page': page})

    def search_people(self, query, page=1):
        return self._get('/search/person', {'query': query, 'page': page})

    def find_by_external_id(self, external_id, external_source):
        return self._get(f'/find/{external_id}', {'external_source': external_source})

    def get_movie(self, tmdb_id, *, use_cache=True):
        return self._get(f'/movie/{tmdb_id}', use_cache=use_cache)

    def get_movie_details(self, tmdb_id, *, use_cache=True):
        """Movie payload with keywords, external ids and watch providers in one request."""
        return self._get_appended(f'/movie/{tmdb_id}', self.MOVIE_APPENDS, use_cache=use_cache)

    def get_movie_credits(self, tmdb_id):
        return self._get(f'/movie/{tmdb_id}/credits')

    def get_movie_recommendations(self, tmdb_id, page=1):
        return self._get(f'/movie/{tmdb_id}/recommendations', {'page': page})

    def get_tv_recommendations(self, tmdb_id, page=1):
        return self._get(f'/tv/{tmdb_id}/recommendations', {'page': page})

    def get_person(self, person_id):
        return self._get(f'/person/{person_id}')

    def get_person_combined_credits(self, person_id):
        return self._get(f'/person/{person_id}/combined_credits')

    def get_person_external_ids(self, person_id):
        return self._get(f'/person/{person_id}/external_ids')

    def get_collection(self, collection_id):
        return self._get(f'/collection/{collection_id}')

    def get_tv_show(self, tmdb_id, *, use_cache=True):
        return self._get(f'/tv/{tmdb_id}', use_cache=use_cache)

    def get_tv_details(self, tmdb_id, *, use_cache=True):
        """Show payload with external ids and watch providers in one request."""
        return self._get_appended(f'/tv/{tmdb_id}', self.TV_APPENDS, use_cache=use_cache)

    def get_tv_aggregate_credits(self, tmdb_id):
        return self._get(f'/tv/{tmdb_id}/aggregate_credits')

    def get_season_aggregate_credits(self, show_id, season_number):
        return self._get(f'/tv/{show_id}/season/{season_number}/aggregate_credits')

    def get_season(self, show_id, season_number, *, use_cache=True, include_credits=True):
        appends = ['credits', 'external_ids'] if include_credits else ['external_ids']
        return self._get_appended(f'/tv/{show_id}/season/{season_number}', appends, use_cache=use_cache)

    def get_season_external_ids(self, show_id, season_number, *, use_cache=True):
        return self._get(f'/tv/{show_id}/season/{season_number}/external_ids', use_cache=use_cache)

    def get_episode_external_ids(self, show_id, season_number, episode_number):
        return self._get(f'/tv/{show_id}/season/{season_number}/episode/{episode_number}/external_ids')

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

    def fetch_seasons(self, tmdb_id, season_numbers, *, use_cache=True):
        """Fetch season payloads (with episodes) keyed by season number.

        Seasons are bundled APPEND_LIMIT per request and batches run in
        parallel; seasons a batch could not deliver are fetched one by one.
        """
        seasons, _ = self._fetch_seasons_with(tmdb_id, season_numbers, use_cache, [])
        return seasons

    def _fetch_seasons_with(self, tmdb_id, season_numbers, use_cache, extra_calls):
        """Run season batches alongside ``extra_calls``; return seasons and the extra results."""
        batches = [
            season_numbers[start:start + self.APPEND_LIMIT]
            for start in range(0, len(season_numbers), self.APPEND_LIMIT)
        ]
        calls = [partial(self._fetch_season_batch, tmdb_id, batch, use_cache) for batch in batches]
        results = run_parallel(calls + list(extra_calls))

        seasons = {}
        for batch, result in zip(batches, results):
            if isinstance(result, Exception):
                logger.warning('Season batch %s failed for tv %s: %s', batch, tmdb_id, result)
            else:
                seasons.update(result)

        leftovers = [number for number in season_numbers if number not in seasons]
        leftover_results = run_parallel([
            partial(self.get_season, tmdb_id, number, use_cache=use_cache, include_credits=False)
            for number in leftovers
        ])
        for number, result in zip(leftovers, leftover_results):
            if isinstance(result, Exception):
                logger.warning('Failed to fetch season %s for tv %s: %s', number, tmdb_id, result)
            elif isinstance(result, dict) and result:
                seasons[number] = result
        return seasons, results[len(batches):]

    def _fetch_season_batch(self, tmdb_id, season_numbers, use_cache):
        data = self._get_appended(
            f'/tv/{tmdb_id}', [f'season/{number}' for number in season_numbers], use_cache=use_cache
        )
        summaries = {
            season.get('season_number'): season
            for season in data.get('seasons') or []
            if isinstance(season, dict)
        }
        seasons = {}
        for number in season_numbers:
            payload = data.get(f'season/{number}')
            if not isinstance(payload, dict) or not payload:
                continue
            summary = summaries.get(number)
            seasons[number] = {**summary, **payload} if isinstance(summary, dict) else payload
        return seasons

    def sync_movie(self, tmdb_id, *, use_cache=True):
        """Fetch movie from TMDB and save/update locally."""
        data = self.get_movie_details(tmdb_id, use_cache=use_cache)
        movie_defaults = {
            'title': data.get('title', ''),
            'overview': data.get('overview', ''),
            'poster_path': data.get('poster_path', '') or '',
            'backdrop_path': data.get('backdrop_path', '') or '',
            'release_date': _parse_date(data.get('release_date')),
            'runtime': data.get('runtime'),
            'vote_average': data.get('vote_average', 0),
            'vote_count': data.get('vote_count', 0),
            'language': data.get('original_language', ''),
            'tagline': data.get('tagline', ''),
            'status': data.get('status', ''),
        }
        keywords_data = data.get('keywords')
        if keywords_data is not None:
            movie_defaults['has_postcredits_scene'] = self._extract_postcredits_scenes(keywords_data)
        movie, _ = Movie.objects.update_or_create(
            tmdb_id=tmdb_id,
            defaults=_non_empty_defaults(movie_defaults),
            create_defaults=movie_defaults,
        )
        self._sync_genres(movie, data.get('genres'))
        return movie

    @classmethod
    def _extract_postcredits_scenes(cls, keywords_data):
        keywords = (keywords_data or {}).get('keywords', [])
        return any(k.get('id') in cls.POSTCREDITS_KEYWORD_IDS for k in keywords if isinstance(k, dict))

    @staticmethod
    def _sync_genres(instance, genres_data):
        names = {
            genre['id']: genre.get('name', '')
            for genre in genres_data or []
            if isinstance(genre, dict) and genre.get('id')
        }
        if not names:
            return
        existing = set(Genre.objects.filter(tmdb_id__in=names).values_list('tmdb_id', flat=True))
        Genre.objects.bulk_create(
            [Genre(tmdb_id=genre_id, name=name) for genre_id, name in names.items() if genre_id not in existing],
            ignore_conflicts=True,
        )
        instance.genres.add(*Genre.objects.filter(tmdb_id__in=names))

    def sync_tv_show(self, tmdb_id, user_id=None, sync_credits: bool = False, *, recompute_user_statuses: bool = True, use_cache: bool = True, only_seasons: list[int] | None = None):
        """Fetch TV show from TMDB and save/update locally, including all seasons and episodes."""
        from .signals import suppress_episode_signals

        data = self.get_tv_details(tmdb_id, use_cache=use_cache)
        season_numbers = [int(n) for n in only_seasons] if only_seasons else self._season_numbers(data)
        show = self._upsert_show(tmdb_id, data)

        stored_ids = dict(
            show.seasons.filter(season_number__in=season_numbers).values_list('season_number', 'external_ids')
        )
        # Bundled season payloads carry no external ids; look them up only for
        # seasons that have none stored, always through the cache.
        needs_ids = [number for number in season_numbers if not stored_ids.get(number)]
        extra_calls = [partial(self.get_season_external_ids, tmdb_id, number) for number in needs_ids]
        extra_calls.append(partial(self._resolve_tvmaze, show, include_episodes=False))
        seasons, extra_results = self._fetch_seasons_with(tmdb_id, season_numbers, use_cache, extra_calls)
        season_ids = {
            number: _external_ids({'external_ids': result})
            for number, result in zip(needs_ids, extra_results)
            if isinstance(result, dict)
        }
        tvmaze_result = extra_results[-1]
        self._apply_tvmaze_metadata(show, None if isinstance(tvmaze_result, Exception) else tvmaze_result[0])

        tvmaze_context: dict[int, tuple[dict | None, list[dict]]] = {}
        with suppress_episode_signals():
            self._sync_genres(show, data.get('genres'))
            for number in season_numbers:
                if number not in seasons:
                    continue
                try:
                    self._upsert_season(
                        show, number, seasons[number],
                        tvmaze_context=tvmaze_context, season_external_ids=season_ids.get(number),
                    )
                except Exception as exc:
                    logger.warning('Failed to sync season %s for tv %s: %s', number, tmdb_id, exc)

        if sync_credits:
            self.sync_show_episode_credits(show, use_cache=use_cache, season_numbers=season_numbers)

        if recompute_user_statuses:
            try:
                from tracking.status_sync import rebuild_episode_chain, refresh_all_statuses_for_show

                rebuild_episode_chain(int(tmdb_id))
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
            'first_air_date': _parse_date(data.get('first_air_date')),
            'last_air_date': _parse_date(data.get('last_air_date')),
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

    def sync_season(self, show, season_number, sync_episode_credits: bool = False, *, use_cache: bool = True, tvmaze_context=None):
        """Fetch a season from TMDB and save/update locally with all episodes."""
        from .signals import episode_signals_suppressed, suppress_episode_signals

        data = self.get_season(show.tmdb_id, season_number, use_cache=use_cache, include_credits=False)
        nested = episode_signals_suppressed()
        with suppress_episode_signals():
            season = self._upsert_season(show, season_number, data, tvmaze_context=tvmaze_context)
        if sync_episode_credits:
            self.sync_show_episode_credits(show, use_cache=use_cache, season_numbers=[season_number])
        if not nested:
            from tracking.status_sync import rebuild_episode_chain

            rebuild_episode_chain(show.tmdb_id)
        return season

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

    def _upsert_season(self, show, season_number: int, data: dict, *, tvmaze_context=None, tvmaze_show=None, tvmaze_episodes=None, season_external_ids=None):
        """Persist one season and its episodes from a TMDB season payload in bulk."""
        season = self._upsert_season_record(show, season_number, data, season_external_ids)
        tvmaze_show, tvmaze_episodes = self._season_tvmaze_context(show, season, tvmaze_context, tvmaze_show, tvmaze_episodes)
        tvmaze_episodes = tvmaze_episodes or []
        episodes_by_number = {(e.get('season'), e.get('number')): e for e in tvmaze_episodes}
        episodes_by_name_date = {
            (self._normalize_title(e.get('name')), e.get('airdate')): e
            for e in tvmaze_episodes
            if e.get('airdate')
        }

        payloads = {
            ep['episode_number']: ep
            for ep in data.get('episodes') or []
            if isinstance(ep, dict) and ep.get('episode_number') is not None
        }
        existing = {episode.episode_number: episode for episode in season.episodes.all()}
        to_create, to_update = [], []
        for episode_number, ep_data in payloads.items():
            defaults = self._episode_defaults(ep_data)
            episode = existing.get(episode_number)
            if episode is None:
                episode = Episode(season=season, episode_number=episode_number, **defaults)
                to_create.append(episode)
            else:
                for field, value in _non_empty_defaults(defaults).items():
                    setattr(episode, field, value)
                to_update.append(episode)

            broadcast_start = None
            remote_ep = episodes_by_number.get((season_number, episode_number))
            if remote_ep is None:
                remote_ep = episodes_by_name_date.get((self._normalize_title(ep_data.get('name')), ep_data.get('air_date')))
            if remote_ep is None and ep_data.get('air_date'):
                candidates = [e for e in tvmaze_episodes if e.get('airdate') == ep_data['air_date']]
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

        Episode.objects.bulk_create(to_create)
        Episode.objects.bulk_update(to_update, EPISODE_FIELDS)

        removed = sorted(set(existing) - set(payloads))
        if removed and payloads:
            self._queue_removed_episode_cleanup(show.tmdb_id, season_number, removed)
        return season

    @staticmethod
    def _queue_removed_episode_cleanup(show_id, season_number, episode_numbers):
        from tracking.tasks.system import cleanup_removed_episodes

        def dispatch():
            try:
                cleanup_removed_episodes.delay(show_id, season_number, episode_numbers)
            except Exception:
                logger.warning('Failed to queue removed episode cleanup for tv %s season %s', show_id, season_number, exc_info=True)

        transaction.on_commit(dispatch)

    @staticmethod
    def _upsert_season_record(show, season_number, data, season_external_ids=None):
        defaults = {
            'tmdb_id': data.get('id', 0), 'name': data.get('name', ''), 'overview': data.get('overview', ''),
            'poster_path': data.get('poster_path', '') or '',
            'external_ids': _external_ids(data) or dict(season_external_ids or {}),
        }
        # A zero vote means "unknown" from TMDB: never let it wipe a stored
        # rating the way _non_empty_defaults guards the other fields.
        if isinstance(data.get('vote_average'), (int, float)) and data.get('vote_average'):
            defaults['vote_average'] = data['vote_average']
        if isinstance(data.get('vote_count'), int) and data.get('vote_count'):
            defaults['vote_count'] = data['vote_count']
        season, _ = Season.objects.update_or_create(
            show=show, season_number=season_number,
            defaults=_non_empty_defaults(defaults), create_defaults=defaults,
        )
        return season

    @staticmethod
    def _episode_defaults(data):
        return {
            'tmdb_id': data.get('id', 0), 'name': data.get('name', ''), 'overview': data.get('overview', ''),
            'still_path': data.get('still_path', '') or '',
            'air_date': _parse_date(data.get('air_date')),
            'runtime': data.get('runtime'), 'vote_average': data.get('vote_average', 0),
            'vote_count': data.get('vote_count', 0), 'episode_type': data.get('episode_type', '') or '',
            'external_ids': _external_ids(data),
        }

    def _season_tvmaze_context(self, show, season, context, tvmaze_show, tvmaze_episodes):
        context = context if context is not None else {season.season_number: (tvmaze_show, tvmaze_episodes or [])}
        if season.season_number not in context:
            parent_tvmaze_id = (show.external_ids or {}).get('tvmaze_id')
            if not season.external_ids:
                # No season-level IDs to match on: reuse the parent show (or
                # skip) instead of firing one TVMaze search per season.
                resolved = tvmaze.lookup_show_by_id(parent_tvmaze_id) if parent_tvmaze_id else None
            else:
                resolved = self._resolve_tvmaze_season(show, season)
                if resolved is None and parent_tvmaze_id:
                    resolved = tvmaze.lookup_show_by_id(parent_tvmaze_id)
            context[season.season_number] = (resolved, self._cached_tvmaze_episodes(context, resolved))
        resolved, episodes = context[season.season_number]
        if resolved and resolved.get('id'):
            season.external_ids['tvmaze_id'] = int(resolved['id'])
            season.save(update_fields=['external_ids'])
        return resolved, episodes

    @staticmethod
    def _cached_tvmaze_episodes(context, resolved):
        """Reuse an already-fetched episode list for the same TVMaze show."""
        if not resolved or not resolved.get('id'):
            return []
        for existing_show, existing_episodes in context.values():
            if isinstance(existing_show, dict) and existing_show.get('id') == resolved.get('id'):
                return existing_episodes
        return tvmaze.get_show_episodes(resolved['id']) if resolved else []

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

    def sync_show_episode_credits(self, show, *, use_cache: bool = True, season_numbers=None):
        """Fetch credits for every stored episode of ``show`` in parallel and save them in bulk.

        Returns ``(synced, failures)``.
        """
        episodes = Episode.objects.filter(season__show=show)
        if season_numbers is not None:
            episodes = episodes.filter(season__season_number__in=season_numbers)
        keys = list(episodes.values_list('id', 'season__season_number', 'episode_number'))
        results = run_parallel([
            partial(self.get_episode_credits, show.tmdb_id, season_number, episode_number, use_cache=use_cache)
            for _, season_number, episode_number in keys
        ])
        fetched = {}
        failures = 0
        for (episode_id, season_number, episode_number), result in zip(keys, results):
            if isinstance(result, Exception):
                failures += 1
                logger.warning('Failed to sync episode credits for tv %s season %s episode %s: %s', show.tmdb_id, season_number, episode_number, result)
            else:
                fetched[episode_id] = result
        self._save_episode_credits(fetched)
        return len(fetched), failures

    def sync_episode_credits(self, show_id, season_number, episode_number, *, show=None, use_cache: bool = True):
        if show is None:
            show = TVShow.objects.filter(tmdb_id=show_id).first() or self.sync_tv_show(show_id, use_cache=use_cache)

        lookup = {'season__show': show, 'season__season_number': season_number, 'episode_number': episode_number}
        episode = Episode.objects.filter(**lookup).first()
        if episode is None:
            self.sync_season(show, season_number, use_cache=use_cache)
            episode = Episode.objects.get(**lookup)

        credits = self.get_episode_credits(show_id, season_number, episode_number, use_cache=use_cache)
        return self._save_episode_credits({episode.id: credits})[episode.id]

    @staticmethod
    def _save_episode_credits(credits_by_episode_id):
        existing = {
            credit.episode_id: credit
            for credit in EpisodeCredit.objects.filter(episode_id__in=credits_by_episode_id)
        }
        to_create, to_update = [], []
        for episode_id, payload in credits_by_episode_id.items():
            payload = payload if isinstance(payload, dict) else {}
            defaults = {field: payload.get(field) or [] for field in CREDIT_FIELDS}
            credit = existing.get(episode_id)
            if credit is None:
                credit = EpisodeCredit(episode_id=episode_id, **defaults)
                to_create.append(credit)
                existing[episode_id] = credit
            else:
                for field, value in _non_empty_defaults(defaults).items():
                    setattr(credit, field, value)
                to_update.append(credit)
        EpisodeCredit.objects.bulk_create(to_create)
        EpisodeCredit.objects.bulk_update(to_update, CREDIT_FIELDS)
        return existing


tmdb = TMDBService()

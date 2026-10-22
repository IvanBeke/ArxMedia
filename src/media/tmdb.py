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
        if use_cache and (cached := cache.get(cache_key)) is not None:
            return cached

        params['api_key'] = self.API_KEY
        response_data = self._request_with_retries(endpoint, params)
        cache.set(cache_key, response_data, self.CACHE_TTL)
        return response_data

    def _request_with_retries(self, endpoint, params):
        for attempt in range(self.REQUEST_RETRIES + 1):
            try:
                return self._perform_request(endpoint, params)
            except requests.RequestException as exc:
                self._rethrow_request_error(exc, endpoint, attempt)
        raise RuntimeError(f'TMDB request failed without response payload for endpoint {endpoint}')

    def _perform_request(self, endpoint, params):
        response = self._session.get(
            f'{self.BASE_URL}{endpoint}',
            params=params,
            timeout=self.REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    def _rethrow_request_error(self, exc, endpoint, attempt):
        should_retry = self._should_retry_request(exc, endpoint)
        if not should_retry or attempt >= self.REQUEST_RETRIES:
            raise exc
        if self._is_server_error(exc) and attempt >= self.SERVER_ERROR_RETRIES:
            raise exc
        time.sleep(min(30, 2**attempt))

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

    def _fetch_seasons_with(self, tmdb_id, season_numbers, use_cache, extra_calls):
        """Run season batches alongside ``extra_calls``; return seasons and the extra results.

        Seasons are bundled APPEND_LIMIT per request and batches run in
        parallel; seasons a batch could not deliver are fetched one by one.
        """
        batches = [
            season_numbers[start:start + self.APPEND_LIMIT]
            for start in range(0, len(season_numbers), self.APPEND_LIMIT)
        ]
        calls = [partial(self._fetch_season_batch, tmdb_id, batch, use_cache) for batch in batches]
        results = run_parallel(calls + list(extra_calls))

        seasons = self._collect_batch_results(tmdb_id, batches, results)
        seasons = self._fetch_missing_seasons(tmdb_id, season_numbers, seasons, use_cache)
        return seasons, results[len(batches):]

    def _collect_batch_results(self, tmdb_id, batches, results):
        seasons = {}
        for batch, result in zip(batches, results, strict=False):
            if isinstance(result, Exception):
                logger.warning('Season batch %s failed for tv %s: %s', batch, tmdb_id, result)
            else:
                seasons.update(result)
        return seasons

    def _fetch_missing_seasons(self, tmdb_id, season_numbers, seasons, use_cache):
        leftovers = [number for number in season_numbers if number not in seasons]
        leftover_results = run_parallel([
            partial(self.get_season, tmdb_id, number, use_cache=use_cache, include_credits=False)
            for number in leftovers
        ])
        for number, result in zip(leftovers, leftover_results, strict=True):
            self._store_fetched_season(tmdb_id, seasons, number, result)
        return seasons

    @staticmethod
    def _store_fetched_season(tmdb_id, seasons, number, result):
        if isinstance(result, Exception):
            logger.warning('Failed to fetch season %s for tv %s: %s', number, tmdb_id, result)
        elif isinstance(result, dict) and result:
            seasons[number] = result

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

    @staticmethod
    def _resolve_language_name(data):
        """Map ``original_language`` code to its display name from the detail payload."""
        code = (data.get('original_language') or '').strip()
        if not code:
            return ''
        for entry in data.get('spoken_languages') or []:
            if not isinstance(entry, dict):
                continue
            if (entry.get('iso_639_1') or '').strip().lower() == code.lower():
                return (entry.get('english_name') or entry.get('name') or '').strip()
        return ''

    def sync_movie(self, tmdb_id, *, use_cache=True):
        """Fetch movie from TMDB and save/update locally."""
        data = self.get_movie_details(tmdb_id, use_cache=use_cache)
        movie_defaults = {
            'title': data.get('title', ''),
            'original_title': data.get('original_title', ''),
            'overview': data.get('overview', ''),
            'poster_path': data.get('poster_path', '') or '',
            'backdrop_path': data.get('backdrop_path', '') or '',
            'release_date': _parse_date(data.get('release_date')),
            'runtime': data.get('runtime'),
            'vote_average': data.get('vote_average', 0),
            'vote_count': data.get('vote_count', 0),
            'language': data.get('original_language', ''),
            'language_name': self._resolve_language_name(data),
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

        seasons, season_ids, parent_tvmaze_show = self._sync_seasons(show, tmdb_id, season_numbers, use_cache)

        tvmaze_context: dict[int | str, tuple[dict | None, list[dict]]] = {}
        with suppress_episode_signals():
            self._sync_genres(show, data.get('genres'))
            self._upsert_synced_seasons(
                show, tmdb_id, season_numbers, seasons, season_ids,
                parent_tvmaze_show, tvmaze_context,
            )

        if sync_credits:
            self.sync_show_episode_credits(show, use_cache=use_cache, season_numbers=season_numbers)
        if recompute_user_statuses:
            self._refresh_user_statuses(tmdb_id, user_id)
        return show

    def _sync_seasons(self, show, tmdb_id, season_numbers, use_cache):
        """Fetch season payloads and TVMaze context, returning everything callers need."""
        # Bundled season payloads carry no external ids; look them up only for
        # seasons that have none stored, always through the cache.
        stored_ids = self._stored_season_ids(show, season_numbers)
        needs_ids = [number for number in season_numbers if not stored_ids.get(number)]
        extra_calls = [partial(self.get_season_external_ids, tmdb_id, number) for number in needs_ids]
        extra_calls.append(partial(self._resolve_tvmaze, show, include_episodes=False))
        seasons, extra_results = self._fetch_seasons_with(tmdb_id, season_numbers, use_cache, extra_calls)
        season_ids = self._season_ids_from_results(needs_ids, extra_results)
        tvmaze_result = extra_results[-1]
        parent_tvmaze_show = tvmaze_result[0] if not isinstance(tvmaze_result, Exception) else None
        self._apply_tvmaze_metadata(show, parent_tvmaze_show)
        return seasons, season_ids, parent_tvmaze_show

    @staticmethod
    def _stored_season_ids(show, season_numbers):
        return dict(
            show.seasons.filter(season_number__in=season_numbers).values_list('season_number', 'external_ids')
        )

    @staticmethod
    def _season_ids_from_results(needs_ids, extra_results):
        return {
            number: _external_ids({'external_ids': result})
            for number, result in zip(needs_ids, extra_results, strict=False)
            if isinstance(result, dict)
        }

    def _upsert_synced_seasons(self, show, tmdb_id, season_numbers, seasons, season_ids, parent_tvmaze_show, tvmaze_context):
        for number in season_numbers:
            if number not in seasons:
                continue
            try:
                self._upsert_season(
                    show, number, seasons[number],
                    tvmaze_context=tvmaze_context, season_external_ids=season_ids.get(number),
                    parent_tvmaze_show=parent_tvmaze_show,
                )
            except Exception as exc:
                logger.warning('Failed to sync season %s for tv %s: %s', number, tmdb_id, exc)

    @staticmethod
    def _refresh_user_statuses(tmdb_id, user_id):
        try:
            from tracking.status_sync import rebuild_episode_chain, refresh_all_statuses_for_show

            rebuild_episode_chain(int(tmdb_id))
            refresh_all_statuses_for_show(int(tmdb_id), current_user_id=user_id)
        except Exception as exc:
            logger.warning('Failed to refresh statuses for tv %s: %s', tmdb_id, exc)

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
            'name': data.get('name', ''), 'original_title': data.get('original_name', ''),
            'overview': data.get('overview', ''),
            'poster_path': data.get('poster_path', '') or '', 'backdrop_path': data.get('backdrop_path', '') or '',
            'first_air_date': _parse_date(data.get('first_air_date')),
            'last_air_date': _parse_date(data.get('last_air_date')),
            'number_of_seasons': data.get('number_of_seasons', 0), 'number_of_episodes': data.get('number_of_episodes', 0),
            'vote_average': data.get('vote_average', 0), 'vote_count': data.get('vote_count', 0),
            'language': data.get('original_language', ''), 'language_name': self._resolve_language_name(data),
            'status': data.get('status', ''),
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

    def _upsert_season(self, show, season_number: int, data: dict, *, tvmaze_context=None, tvmaze_show=None, tvmaze_episodes=None, season_external_ids=None, parent_tvmaze_show=None):
        """Persist one season and its episodes from a TMDB season payload in bulk."""
        season = self._upsert_season_record(show, season_number, data, season_external_ids)
        payloads = self._episode_payloads(data)
        tvmaze_show, tvmaze_episodes = self._season_tvmaze_context(
            show, season, tvmaze_context, tvmaze_show, tvmaze_episodes, payloads=payloads,
            parent_tvmaze_show=parent_tvmaze_show,
        )
        tvmaze_episodes = tvmaze_episodes or []
        allow_single_season_number = self._allow_single_season_number(show, tvmaze_show, tvmaze_episodes)
        existing = self._existing_episodes(season)
        to_create, to_update = self._collect_episode_changes(
            season, existing, payloads, season_number=season_number,
            tvmaze_show=tvmaze_show, tvmaze_episodes=tvmaze_episodes,
            allow_single_season_number=allow_single_season_number,
        )
        Episode.objects.bulk_create(to_create)
        Episode.objects.bulk_update(to_update, EPISODE_FIELDS)
        self._cleanup_removed_episodes(show, season_number, payloads, existing)
        return season

    @staticmethod
    def _existing_episodes(season):
        return {episode.episode_number: episode for episode in season.episodes.all()}

    @staticmethod
    def _episode_payloads(data):
        return {
            ep['episode_number']: ep
            for ep in data.get('episodes') or []
            if isinstance(ep, dict) and ep.get('episode_number') is not None
        }

    @staticmethod
    def _allow_single_season_number(show, tvmaze_show, tvmaze_episodes):
        if not tvmaze_episodes or TMDBService._is_tvmaze_parent_show(show, tvmaze_show):
            return False
        return len({e.get('season') for e in tvmaze_episodes}) == 1

    @staticmethod
    def _is_tvmaze_parent_show(show, tvmaze_show):
        parent_tvmaze_id = (show.external_ids or {}).get('tvmaze_id')
        return bool(
            tvmaze_show
            and tvmaze_show.get('id') is not None
            and tvmaze_show.get('id') == parent_tvmaze_id
        )

    @staticmethod
    def _cleanup_removed_episodes(show, season_number, payloads, existing):
        removed = sorted(set(existing) - set(payloads))
        if removed and payloads:
            TMDBService._queue_removed_episode_cleanup(show.tmdb_id, season_number, removed)

    def _collect_episode_changes(self, season, existing, payloads, *, season_number, tvmaze_show, tvmaze_episodes, allow_single_season_number):
        to_create, to_update = [], []
        for episode_number, ep_data in payloads.items():
            episode = existing.get(episode_number)
            defaults = self._episode_defaults(ep_data, episode)
            if episode is None:
                episode = Episode(season=season, episode_number=episode_number, **defaults)
                to_create.append(episode)
            else:
                for field, value in _non_empty_defaults(defaults).items():
                    setattr(episode, field, value)
                to_update.append(episode)

            self._apply_tvmaze_episode_match(
                episode, season_number, ep_data,
                tvmaze_show=tvmaze_show, tvmaze_episodes=tvmaze_episodes,
                allow_single_season_number=allow_single_season_number, payloads=payloads,
            )
        return to_create, to_update

    def _apply_tvmaze_episode_match(self, episode, season_number, ep_data, *, tvmaze_show, tvmaze_episodes, allow_single_season_number, payloads):
        """Update ``episode`` in place with TVMaze ids, broadcast time and runtime."""
        remote_ep = self._find_tvmaze_episode(
            season_number, ep_data, tvmaze_episodes,
            allow_single_season_number=allow_single_season_number, payloads=payloads,
        )
        if remote_ep is None:
            self._apply_schedule_fallback(episode, ep_data, tvmaze_show)
            return
        self._apply_tvmaze_match(episode, ep_data, tvmaze_show, remote_ep)

    @staticmethod
    def _apply_schedule_fallback(episode, ep_data, tvmaze_show):
        if tvmaze_show:
            episode.broadcast_start = tvmaze.parse_show_schedule_datetime(tvmaze_show, ep_data.get('air_date'))

    @staticmethod
    def _apply_tvmaze_match(episode, ep_data, tvmaze_show, remote_ep):
        tvmaze_payload = tvmaze.normalize_episode_from_tvmaze(tvmaze_show, remote_ep)
        if not tvmaze_payload:
            return
        episode.external_ids = TMDBService._episode_tvmaze_ids(episode, remote_ep, tvmaze_show)
        broadcast_start = tvmaze_payload.get('broadcast_start')
        if not remote_ep.get('airtime'):
            broadcast_start = tvmaze.parse_show_schedule_datetime(tvmaze_show, ep_data.get('air_date'))
        episode.broadcast_start = broadcast_start
        episode.runtime = episode.runtime or tvmaze_payload.get('runtime')

    @staticmethod
    def _episode_tvmaze_ids(episode, remote_ep, tvmaze_show):
        external_ids = dict(episode.external_ids or {})
        if remote_ep.get('id') is not None:
            external_ids['tvmaze_id'] = remote_ep['id']
        if tvmaze_show and tvmaze_show.get('id') is not None:
            external_ids['tvmaze_show_id'] = int(tvmaze_show['id'])
        return external_ids

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
        existing = Season.objects.filter(show=show, season_number=season_number).only('external_ids').first()
        external_ids = dict(existing.external_ids or {}) if existing else {}
        external_ids.update(_external_ids(data))
        external_ids.update(season_external_ids or {})
        defaults = {
            'tmdb_id': data.get('id', 0), 'name': data.get('name', ''), 'overview': data.get('overview', ''),
            'poster_path': data.get('poster_path', '') or '',
            'external_ids': external_ids,
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
    def _episode_defaults(data, existing=None):
        external_ids = dict(existing.external_ids or {}) if existing is not None else {}
        external_ids.update(_external_ids(data))
        return {
            'tmdb_id': data.get('id', 0), 'name': data.get('name', ''), 'overview': data.get('overview', ''),
            'still_path': data.get('still_path', '') or '',
            'air_date': _parse_date(data.get('air_date')),
            'runtime': data.get('runtime'), 'vote_average': data.get('vote_average', 0),
            'vote_count': data.get('vote_count', 0), 'episode_type': data.get('episode_type', '') or '',
            'external_ids': external_ids,
        }

    def _season_tvmaze_context(self, show, season, context, tvmaze_show, tvmaze_episodes, *, payloads=None, parent_tvmaze_show=None):
        season_key = season.season_number
        if context is None:
            context = {season_key: (tvmaze_show, tvmaze_episodes or [])}
        if season_key not in context:
            context[season_key] = self._load_season_tvmaze(show, season, context, payloads, parent_tvmaze_show)
        resolved, episodes = context[season_key]
        TMDBService._store_season_tvmaze_id(season, resolved)
        return resolved, episodes

    @staticmethod
    def _store_season_tvmaze_id(season, resolved):
        if not (resolved and resolved.get('id')):
            return
        season.external_ids = dict(season.external_ids or {})
        season.external_ids['tvmaze_id'] = int(resolved['id'])
        season.save(update_fields=['external_ids'])

    def _load_season_tvmaze(self, show, season, context, payloads, parent_tvmaze_show):
        parent_show, parent_episodes = self._season_tvmaze_basics(show, context, parent_tvmaze_show)
        parent_tvmaze_id = (show.external_ids or {}).get('tvmaze_id')
        resolve, resolve_from_stored = self._resolve_for_season(
            show, season, context, payloads, parent_show, parent_episodes, parent_tvmaze_id,
        )
        return self._validate_season_resolution(
            season, context, payloads, resolve, resolve_from_stored, parent_show, parent_episodes,
        )

    def _season_tvmaze_basics(self, show, context, parent_tvmaze_show):
        parent_tvmaze_id = (show.external_ids or {}).get('tvmaze_id')
        parent_show = parent_tvmaze_show or (
            tvmaze.lookup_show_by_id(parent_tvmaze_id) if parent_tvmaze_id else None
        )
        parent_episodes = self._cached_tvmaze_episodes(context, parent_show)
        return parent_show, parent_episodes

    def _resolve_for_season(self, show, season, context, payloads, parent_show, parent_episodes, parent_tvmaze_id):
        parent_covered = self._parent_covers_season(season, payloads, parent_show, parent_episodes)
        if self._trusted_stored_tvmaze_id(season, parent_tvmaze_id):
            return self._resolve_with_stored_id(show, season, context, payloads, parent_show, parent_covered)
        if parent_covered:
            # A named season can still belong to the parent show (for
            # example arc-based season names), so check its episodes first.
            return parent_show, False
        if self._consider_fallback_lookup(season, payloads, parent_show, parent_covered):
            # Seasons not covered by the parent are looked up concretely.
            # Candidate acceptance still depends on episode metadata.
            return self._resolve_tvmaze_season(show, season, use_stored_id=False), False
        if not (season.external_ids or {}):
            # No season-level IDs to match on: reuse the parent show (or
            # skip) instead of firing one TVMaze search per season.
            return parent_show, False
        return None, False

    def _parent_covers_season(self, season, payloads, parent_show, parent_episodes):
        return bool(
            parent_show and self._tvmaze_show_covers_season(season.season_number, payloads, parent_episodes)
        )

    @staticmethod
    def _trusted_stored_tvmaze_id(season, parent_tvmaze_id):
        stored_tvmaze_id = (season.external_ids or {}).get('tvmaze_id')
        return bool(stored_tvmaze_id and stored_tvmaze_id != parent_tvmaze_id)

    @staticmethod
    def _consider_fallback_lookup(season, payloads, parent_show, parent_covered):
        season_ids = season.external_ids or {}
        if any(season_ids.get(key) for key in EXTERNAL_ID_KEYS):
            return True
        return bool(parent_show) and bool(payloads) and not parent_covered

    def _resolve_with_stored_id(self, show, season, context, payloads, parent_show, parent_covered):
        resolved = tvmaze.lookup_show_by_id((season.external_ids or {})['tvmaze_id'])
        resolved, resolved_from_stored = self._accepted_stored_id_resolution(season, context, payloads, resolved)
        if resolved is not None:
            return resolved, resolved_from_stored
        if self._consider_fallback_lookup(season, payloads, parent_show, parent_covered):
            return self._resolve_tvmaze_season(show, season, use_stored_id=False), False
        return None, False

    def _accepted_stored_id_resolution(self, season, context, payloads, resolved):
        """Accept the stored-id resolution unless its episodes vote it out."""
        if payloads and resolved is not None and not self._stored_id_show_matches(season, context, resolved, payloads):
            return None, False
        return resolved, resolved is not None

    def _stored_id_show_matches(self, season, context, resolved, payloads):
        stored_episodes = self._cached_tvmaze_episodes(context, resolved)
        return self._tvmaze_show_matches_season_episodes(season.season_number, payloads, stored_episodes)

    def _validate_season_resolution(self, season, context, payloads, resolved, resolved_from_stored, parent_show, parent_episodes):
        episodes = parent_episodes if resolved is parent_show else self._cached_tvmaze_episodes(context, resolved)
        if self._reject_unverified_candidate(
            season.season_number, payloads, resolved, resolved_from_stored, parent_show, episodes,
        ):
            resolved, episodes = parent_show, parent_episodes
        if resolved is None and parent_show:
            resolved, episodes = parent_show, parent_episodes
        return resolved, episodes

    @staticmethod
    def _reject_unverified_candidate(season_number, payloads, resolved, resolved_from_stored, parent_show, episodes):
        if not resolved or resolved is parent_show or resolved_from_stored:
            return False
        return bool(
            payloads
            and not TMDBService._tvmaze_show_matches_season_episodes(season_number, payloads, episodes)
        )

    @staticmethod
    def _cached_tvmaze_episodes(context, resolved):
        """Reuse an already-fetched episode list for the same TVMaze show."""
        if not resolved or not resolved.get('id'):
            return []
        for existing_show, existing_episodes in context.values():
            if isinstance(existing_show, dict) and existing_show.get('id') == resolved.get('id'):
                return existing_episodes
        episodes = tvmaze.get_show_episodes(resolved['id'])
        context[f'__show__{resolved["id"]}'] = (resolved, episodes)
        return episodes

    @staticmethod
    def _normalize_title(value):
        return ' '.join(str(value or '').casefold().replace('-', ' ').split())

    @staticmethod
    def _episode_matches_airdate_and_name(remote, air_date, name):
        return remote.get('airdate') == air_date and TMDBService._normalize_title(remote.get('name')) == name

    @staticmethod
    def _unique_airdate_match(tvmaze_episodes, air_date, payloads=None):
        if payloads is not None:
            payload_count = sum(1 for ep_data in payloads.values() if ep_data.get('air_date') == air_date)
            if payload_count != 1:
                return None
        candidates = [remote for remote in tvmaze_episodes if remote.get('airdate') == air_date]
        return candidates[0] if len(candidates) == 1 else None

    @staticmethod
    def _single_season_number_match(tvmaze_episodes, episode_number):
        return next((remote for remote in tvmaze_episodes if remote.get('number') == episode_number), None)

    @classmethod
    def _find_tvmaze_episode(cls, season_number, ep_data, tvmaze_episodes, *, allow_single_season_number=False, payloads=None):
        episode_number = ep_data.get('episode_number')
        if episode_number is None:
            return None
        air_date = ep_data.get('air_date')
        if air_date:
            match = cls._match_by_airdate(
                tvmaze_episodes, air_date, cls._normalize_title(ep_data.get('name')), payloads,
            )
            if match is not None:
                return match
        return cls._match_single_season_remote(
            tvmaze_episodes, episode_number, allow_single_season_number,
        )

    @classmethod
    def _match_by_airdate_and_name(cls, tvmaze_episodes, air_date, name):
        if not (air_date and name):
            return None
        for remote in tvmaze_episodes:
            if cls._episode_matches_airdate_and_name(remote, air_date, name):
                return remote
        return None

    @classmethod
    def _match_by_airdate(cls, tvmaze_episodes, air_date, name, payloads):
        named_match = cls._match_by_airdate_and_name(tvmaze_episodes, air_date, name)
        if named_match:
            return named_match
        return cls._unique_airdate_match(tvmaze_episodes, air_date, payloads)

    @staticmethod
    def _match_single_season_remote(tvmaze_episodes, episode_number, allow_single_season_number):
        single_season = (
            allow_single_season_number
            and len({remote.get('season') for remote in tvmaze_episodes}) == 1
        )
        if not single_season:
            return None
        return TMDBService._single_season_number_match(tvmaze_episodes, episode_number)

    @classmethod
    def _tvmaze_show_covers_season(cls, season_number, payloads, tvmaze_episodes):
        if not payloads or not tvmaze_episodes:
            return False
        parent_season = [episode for episode in tvmaze_episodes if episode.get('season') == season_number]
        if not parent_season:
            return False
        matches = sum(
            1 for ep_data in payloads.values()
            if cls._find_tvmaze_episode(
                season_number, ep_data, tvmaze_episodes, payloads=payloads
            )
        )
        if not matches:
            return False
        if len(parent_season) == len(payloads):
            return True
        # Count mismatches can come from specials or an outdated TVMaze
        # season. Keep the parent only when every TMDB payload episode can
        # be matched; a partial match is not enough to reuse the parent.
        return matches == len(payloads) and len(payloads) > 0

    @classmethod
    def _tvmaze_show_matches_season_episodes(cls, season_number, payloads, tvmaze_episodes):
        if not payloads or not tvmaze_episodes:
            return False
        payload_dates = {ep_data.get('air_date') for ep_data in payloads.values() if ep_data.get('air_date')}
        episode_dates = {remote.get('airdate') for remote in tvmaze_episodes if remote.get('airdate')}
        allow_single_season_number = (
            len({remote.get('season') for remote in tvmaze_episodes}) == 1
            and len(tvmaze_episodes) == len(payloads)
            and bool(payload_dates)
            and payload_dates == episode_dates
        )
        matches = sum(
            1 for ep_data in payloads.values()
            if cls._find_tvmaze_episode(
                season_number,
                ep_data,
                tvmaze_episodes,
                allow_single_season_number=allow_single_season_number,
                payloads=payloads,
            )
        )
        if allow_single_season_number:
            return matches == len(payloads)
        return matches == len(payloads)

    @classmethod
    def _tvmaze_show_matches_season(cls, season, candidate):
        candidate_name = cls._normalize_title((candidate or {}).get('name'))
        season_name = cls._normalize_title(season.name)
        return bool(candidate_name and season_name and season_name in candidate_name)

    def _resolve_tvmaze_season(self, show, season, *, use_stored_id=True):
        season_ids = season.external_ids or {}
        if use_stored_id and season_ids.get('tvmaze_id'):
            return tvmaze.lookup_show_by_id(season_ids['tvmaze_id'])
        external_ids = {
            key: season_ids.get(key)
            for key in EXTERNAL_ID_KEYS
            if season_ids.get(key)
        }
        candidate = tvmaze.lookup_season_show(
            external_ids=external_ids or None,
            season_name=season.name,
            year=season.air_date.year if season.air_date else None,
        )
        if candidate is None or external_ids:
            return candidate
        return candidate if self._tvmaze_show_matches_season(season, candidate) else None

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
        for (episode_id, season_number, episode_number), result in zip(keys, results, strict=True):
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

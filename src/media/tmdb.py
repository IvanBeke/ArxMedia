import json
import logging

import redis
import requests
from django.conf import settings
from django.utils.dateparse import parse_date

from .models import Episode, EpisodeCredit, Genre, Movie, Season, TVShow

logger = logging.getLogger(__name__)


class TMDBService:
    BASE_URL = getattr(settings, 'TMDB_BASE_URL', 'https://api.themoviedb.org/3')
    API_KEY = getattr(settings, 'TMDB_API_KEY', '')
    CACHE_TTL = 604800  # 7 days

    def __init__(self):
        self._redis = None

    def _get_redis(self):
        if self._redis is None:
            url = getattr(settings, 'REDIS_URL', None)
            if url:
                self._redis = redis.from_url(url, decode_responses=True)
        return self._redis

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
        response = requests.get(f'{self.BASE_URL}{endpoint}', params=params)
        response.raise_for_status()
        data = response.json()

        if r and use_cache:
            try:
                r.set(cache_key, json.dumps(data), nx=True, ex=self.CACHE_TTL)
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

    def get_movie(self, tmdb_id):
        return self._get(f'/movie/{tmdb_id}', {'append_to_response': 'credits,videos'})

    def get_movie_credits(self, tmdb_id):
        return self._get(f'/movie/{tmdb_id}/credits')

    def get_tv_show(self, tmdb_id):
        return self._get(f'/tv/{tmdb_id}', {'append_to_response': 'credits,videos'})

    def get_tv_aggregate_credits(self, tmdb_id):
        return self._get(f'/tv/{tmdb_id}/aggregate_credits')

    def get_movie_watch_providers(self, tmdb_id):
        return self._get(f'/movie/{tmdb_id}/watch/providers')

    def get_tv_watch_providers(self, tmdb_id):
        return self._get(f'/tv/{tmdb_id}/watch/providers')

    def get_season(self, show_id, season_number):
        return self._get(f'/tv/{show_id}/season/{season_number}', {'append_to_response': 'credits'})

    def get_episode_credits(self, show_id, season_number, episode_number):
        return self._get(f'/tv/{show_id}/season/{season_number}/episode/{episode_number}/credits')

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

    def sync_movie(self, tmdb_id):
        """Fetch movie from TMDB and save/update locally."""
        data = self.get_movie(tmdb_id)
        movie, _ = Movie.objects.update_or_create(
            tmdb_id=tmdb_id,
            defaults={
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
        )
        for g in data.get('genres', []):
            genre, _ = Genre.objects.get_or_create(tmdb_id=g['id'], defaults={'name': g['name']})
            movie.genres.add(genre)
        return movie

    def sync_tv_show(self, tmdb_id):
        """Fetch TV show from TMDB and save/update locally."""
        data = self.get_tv_show(tmdb_id)
        networks = ', '.join([n['name'] for n in data.get('networks', [])])
        show, _ = TVShow.objects.update_or_create(
            tmdb_id=tmdb_id,
            defaults={
                'name': data.get('name', ''),
                'overview': data.get('overview', ''),
                'poster_path': data.get('poster_path', '') or '',
                'backdrop_path': data.get('backdrop_path', '') or '',
                'first_air_date': parse_date(data['first_air_date']) if data.get('first_air_date') else None,
                'last_air_date': parse_date(data['last_air_date']) if data.get('last_air_date') else None,
                'number_of_seasons': data.get('number_of_seasons', 0),
                'number_of_episodes': data.get('number_of_episodes', 0),
                'vote_average': data.get('vote_average', 0),
                'vote_count': data.get('vote_count', 0),
                'language': data.get('original_language', ''),
                'status': data.get('status', ''),
                'networks': networks,
            }
        )
        for g in data.get('genres', []):
            genre, _ = Genre.objects.get_or_create(tmdb_id=g['id'], defaults={'name': g['name']})
            show.genres.add(genre)
        return show

    def sync_season(self, show, season_number):
        """Fetch a season from TMDB and save/update locally with all episodes."""
        data = self.get_season(show.tmdb_id, season_number)
        season, _ = Season.objects.update_or_create(
            show=show,
            season_number=season_number,
            defaults={
                'tmdb_id': data.get('id', 0),
                'name': data.get('name', ''),
                'overview': data.get('overview', ''),
                'poster_path': data.get('poster_path', '') or '',
                'air_date': parse_date(data['air_date']) if data.get('air_date') else None,
                'episode_count': data.get('episode_count', 0),
            }
        )
        for ep_data in data.get('episodes', []):
            episode, _ = Episode.objects.update_or_create(
                season=season,
                episode_number=ep_data['episode_number'],
                defaults={
                    'tmdb_id': ep_data.get('id', 0),
                    'name': ep_data.get('name', ''),
                    'overview': ep_data.get('overview', ''),
                    'still_path': ep_data.get('still_path', '') or '',
                    'air_date': parse_date(ep_data['air_date']) if ep_data.get('air_date') else None,
                    'runtime': ep_data.get('runtime'),
                    'vote_average': ep_data.get('vote_average', 0),
                    'vote_count': ep_data.get('vote_count', 0),
                }
            )

            credit_defaults = {}
            if 'cast' in ep_data:
                credit_defaults['cast'] = ep_data.get('cast') or []
            if 'crew' in ep_data:
                credit_defaults['crew'] = ep_data.get('crew') or []
            if 'guest_stars' in ep_data:
                credit_defaults['guest_stars'] = ep_data.get('guest_stars') or []
            if credit_defaults:
                EpisodeCredit.objects.update_or_create(
                    episode=episode,
                    defaults=credit_defaults,
                )
        return season

    def sync_episode_credits(self, show_id, season_number, episode_number, *, show=None):
        if show is None:
            show = TVShow.objects.filter(tmdb_id=show_id).first() or self.sync_tv_show(show_id)

        season = show.seasons.filter(season_number=season_number).first()
        if season is None:
            season = self.sync_season(show, season_number)

        episode = season.episodes.filter(episode_number=episode_number).first()
        if episode is None:
            season = self.sync_season(show, season_number)
            episode = season.episodes.get(episode_number=episode_number)

        credits = self.get_episode_credits(show_id, season_number, episode_number)
        episode_credit, _ = EpisodeCredit.objects.update_or_create(
            episode=episode,
            defaults={
                'cast': credits.get('cast') or [],
                'crew': credits.get('crew') or [],
                'guest_stars': credits.get('guest_stars') or [],
            },
        )
        return episode_credit


tmdb = TMDBService()

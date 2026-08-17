from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from tracking.models import Rating, WatchEntry, Watchlist

from media.models import Movie, TVShow

User = get_user_model()


class MediaTests(TestCase):
    @staticmethod
    def _fake_tmdb_get(endpoint, params=None):
        if endpoint == '/movie/popular':
            return {'results': [], 'page': 1, 'total_pages': 1, 'total_results': 0}
        if endpoint == '/tv/popular':
            return {'results': [], 'page': 1, 'total_pages': 1, 'total_results': 0}
        if endpoint == '/search/multi':
            return {'results': [], 'page': 1, 'total_pages': 1, 'total_results': 0}
        if endpoint.startswith('/trending/'):
            return {'results': [], 'page': 1, 'total_pages': 1, 'total_results': 0}

        if endpoint == '/movie/550':
            return {
                'id': 550,
                'title': 'Fight Club',
                'overview': 'Mocked movie',
                'release_date': '1999-10-15',
                'genres': [],
            }
        if endpoint == '/movie/550/watch/providers':
            return {'results': {}}

        if endpoint == '/tv/1399':
            return {
                'id': 1399,
                'name': 'Game of Thrones',
                'overview': 'Mocked show',
                'first_air_date': '2011-04-17',
                'number_of_seasons': 1,
                'number_of_episodes': 1,
                'genres': [],
                'networks': [],
            }
        if endpoint == '/tv/1399/watch/providers':
            return {'results': {}}
        if endpoint == '/tv/1399/season/1':
            return {
                'id': 139901,
                'season_number': 1,
                'name': 'Season 1',
                'episode_count': 1,
                'episodes': [
                    {
                        'id': 13990101,
                        'episode_number': 1,
                        'name': 'Winter Is Coming',
                        'air_date': '2011-04-17',
                    }
                ],
            }
        if endpoint == '/tv/1399/season/1/episode/1/credits':
            return {'cast': [], 'crew': []}

        return {}

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = APIClient()
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        self.tmdb_patcher = patch('media.tmdb.TMDBService._get', side_effect=self._fake_tmdb_get)
        self.tmdb_patcher.start()

    def tearDown(self):
        self.tmdb_patcher.stop()

    def test_movie_popular(self):
        response = self.client.get('/api/media/popular/?type=movie')
        self.assertEqual(response.status_code, 200)

    def test_movie_detail(self):
        response = self.client.get('/api/media/movies/550/')  # Fight Club
        self.assertIn(response.status_code, [200, 404])

    def test_tv_popular(self):
        response = self.client.get('/api/media/popular/?type=tv')
        self.assertEqual(response.status_code, 200)

    def test_tv_detail(self):
        response = self.client.get('/api/media/tv/1399/')  # Game of Thrones
        self.assertIn(response.status_code, [200, 404])

    def test_search(self):
        response = self.client.get('/api/media/search/?q=inception')
        self.assertEqual(response.status_code, 200)

    def test_trending(self):
        response = self.client.get('/api/media/trending/')
        self.assertEqual(response.status_code, 200)

    def test_season_detail(self):
        response = self.client.get('/api/media/tv/1399/seasons/1/')
        self.assertEqual(response.status_code, 200)

    def test_episode_detail(self):
        response = self.client.get('/api/media/tv/1399/seasons/1/episodes/1/credits/')
        self.assertEqual(response.status_code, 200)

    @patch('media.views.tmdb.sync_season')
    @patch('media.views.tmdb.get_tv_watch_providers')
    def test_tv_detail_uses_user_preferred_region_when_region_missing(self, mock_providers, mock_sync_season):
        self.user.preferred_region = 'ES'
        self.user.save(update_fields=['preferred_region'])

        TVShow.objects.create(
            tmdb_id=99999,
            name='Demo Show',
            number_of_seasons=0,
            number_of_episodes=0,
        )

        mock_providers.return_value = {
            'results': {
                'ES': {
                    'link': 'https://example.com/es',
                    'flatrate': [{'provider_id': 1, 'provider_name': 'Demo ES'}],
                }
            }
        }

        response = self.client.get('/api/media/tv/99999/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['watch_providers']['region'], 'ES')

    @patch('media.views.tmdb.get_popular_movies')
    def test_popular_movies_includes_user_status_for_authenticated_user(self, mock_popular):
        mock_popular.return_value = {
            'results': [
                {'id': 101, 'title': 'Movie A'},
                {'id': 102, 'title': 'Movie B'},
            ],
            'page': 1,
            'total_pages': 1,
            'total_results': 2,
        }
        Watchlist.objects.create(user=self.user, media_type='movie', tmdb_id=101)
        WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=102, status='watched', watched_at='2026-08-01T10:00:00Z')
        Rating.objects.create(user=self.user, media_type='movie', tmdb_id=102, score=9)

        response = self.client.get('/api/media/popular/?type=movie')
        self.assertEqual(response.status_code, 200)
        first, second = response.data['results']
        self.assertEqual(first['user_status']['status'], 'plan_to_watch')
        self.assertEqual(second['user_status']['status'], 'watched')
        self.assertEqual(second['user_status']['rating'], 9)

    @patch('media.views.tmdb.search_multi')
    def test_search_multi_annotates_only_movie_and_tv(self, mock_search_multi):
        mock_search_multi.return_value = {
            'results': [
                {'id': 201, 'media_type': 'movie', 'title': 'Movie'},
                {'id': 202, 'media_type': 'tv', 'name': 'Show'},
                {'id': 203, 'media_type': 'person', 'name': 'Actor'},
            ],
            'page': 1,
            'total_pages': 1,
            'total_results': 3,
        }
        Watchlist.objects.create(user=self.user, media_type='movie', tmdb_id=201)
        Watchlist.objects.create(user=self.user, media_type='tv', tmdb_id=202)

        response = self.client.get('/api/media/search/?q=test&type=multi')
        self.assertEqual(response.status_code, 200)
        results = response.data['results']
        movie_entry = next(item for item in results if item['id'] == 201)
        tv_entry = next(item for item in results if item['id'] == 202)
        person_entry = next(item for item in results if item['id'] == 203)
        self.assertEqual(movie_entry['user_status']['status'], 'plan_to_watch')
        self.assertEqual(tv_entry['user_status']['status'], 'plan_to_watch')
        self.assertNotIn('user_status', person_entry)

    @patch('media.views.tmdb.get_popular_tv')
    def test_popular_tv_status_rules_exclude_season_zero_for_show_progress(self, mock_popular):
        mock_popular.return_value = {
            'results': [{'id': 303, 'name': 'Show A'}],
            'page': 1,
            'total_pages': 1,
            'total_results': 1,
        }

        show = TVShow.objects.create(
            tmdb_id=303,
            name='Show A',
            number_of_seasons=2,
            number_of_episodes=3,
            status='Ended',
        )
        season_zero = show.seasons.create(tmdb_id=3000, season_number=0, name='Specials')
        season_one = show.seasons.create(tmdb_id=3001, season_number=1, name='Season 1')
        season_two = show.seasons.create(tmdb_id=3002, season_number=2, name='Season 2')
        season_zero.episodes.create(tmdb_id=1, episode_number=1, name='Special 1')
        season_one.episodes.create(tmdb_id=2, episode_number=1, name='Ep 1')
        season_one.episodes.create(tmdb_id=3, episode_number=2, name='Ep 2')
        season_two.episodes.create(tmdb_id=4, episode_number=1, name='Ep 1')

        # Only specials watched -> show should still be none
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=303,
            season_number=0,
            episode_number=1,
            status='watched',
            watched_at='2026-08-01T10:00:00Z',
        )

        response = self.client.get('/api/media/popular/?type=tv')
        self.assertEqual(response.status_code, 200)
        status_payload = response.data['results'][0]['user_status']
        self.assertEqual(status_payload['status'], 'none')
        self.assertEqual(status_payload['progress']['total_episodes'], 3)
        self.assertEqual(status_payload['progress']['watched_episodes'], 0)

        # Watch one non-special -> watching
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=303,
            season_number=1,
            episode_number=1,
            status='watched',
            watched_at='2026-08-02T10:00:00Z',
        )
        response = self.client.get('/api/media/popular/?type=tv')
        self.assertEqual(response.data['results'][0]['user_status']['status'], 'watching')

        # Watch remaining non-special -> watched
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=303,
            season_number=1,
            episode_number=2,
            status='watched',
            watched_at='2026-08-03T10:00:00Z',
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=303,
            season_number=2,
            episode_number=1,
            status='watched',
            watched_at='2026-08-04T10:00:00Z',
        )
        response = self.client.get('/api/media/popular/?type=tv')
        self.assertEqual(response.data['results'][0]['user_status']['status'], 'watched')

    @patch('media.views.tmdb.get_season')
    def test_season_detail_includes_season_zero_own_progress(self, mock_get_season):
        show = TVShow.objects.create(tmdb_id=404, name='Show B', number_of_seasons=1, number_of_episodes=2)
        season_zero = show.seasons.create(tmdb_id=4040, season_number=0, name='Specials')
        season_zero.episodes.create(tmdb_id=10, episode_number=1, name='S0E1')
        season_zero.episodes.create(tmdb_id=11, episode_number=2, name='S0E2')

        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=404,
            season_number=0,
            episode_number=1,
            status='watched',
            watched_at='2026-08-01T10:00:00Z',
        )

        mock_get_season.return_value = {
            'id': 4040,
            'season_number': 0,
            'name': 'Specials',
            'episodes': [],
        }

        response = self.client.get('/api/media/tv/404/seasons/0/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['user_status']['status'], 'watching')
        self.assertEqual(response.data['user_status']['progress']['watched_episodes'], 1)
        self.assertEqual(response.data['user_status']['progress']['total_episodes'], 2)

    @patch('media.views.tmdb.get_popular_movies')
    def test_media_endpoints_require_authentication(self, mock_popular):
        anon = APIClient()
        mock_popular.return_value = {
            'results': [{'id': 555, 'title': 'Anon Movie'}],
            'page': 1,
            'total_pages': 1,
            'total_results': 1,
        }

        self.assertEqual(anon.get('/api/media/search/?q=test').status_code, 401)
        self.assertEqual(anon.get('/api/media/trending/').status_code, 401)
        self.assertEqual(anon.get('/api/media/popular/?type=movie').status_code, 401)
        self.assertEqual(anon.get('/api/media/movies/550/').status_code, 401)
        self.assertEqual(anon.get('/api/media/movies/550/credits/').status_code, 401)
        self.assertEqual(anon.get('/api/media/tv/1399/').status_code, 401)
        self.assertEqual(anon.get('/api/media/tv/1399/credits/').status_code, 401)
        self.assertEqual(anon.get('/api/media/tv/1399/seasons/1/').status_code, 401)
        self.assertEqual(anon.get('/api/media/tv/1399/seasons/1/episodes/1/credits/').status_code, 401)

    @patch('media.views.tmdb.sync_movie')
    @patch('media.views.tmdb.get_movie_watch_providers')
    def test_movie_detail_includes_user_status(self, mock_providers, mock_sync_movie):
        from media.models import Movie
        Movie.objects.create(tmdb_id=777, title='Movie Detail')
        Watchlist.objects.create(user=self.user, media_type='movie', tmdb_id=777)
        Rating.objects.create(user=self.user, media_type='movie', tmdb_id=777, score=7)
        mock_providers.return_value = {}

        response = self.client.get('/api/media/movies/777/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['user_status']['status'], 'plan_to_watch')
        self.assertEqual(response.data['user_status']['rating'], 7)

    @patch('media.views.tmdb.sync_tv_show')
    @patch('media.views.tmdb.get_tv_watch_providers')
    def test_tv_detail_status_watching_and_dropped(self, mock_providers, mock_sync_tv_show):
        show = TVShow.objects.create(tmdb_id=888, name='Show Detail', number_of_seasons=1, number_of_episodes=2)
        season = show.seasons.create(tmdb_id=8881, season_number=1, name='Season 1')
        season.episodes.create(tmdb_id=88811, episode_number=1, name='Ep 1')
        season.episodes.create(tmdb_id=88812, episode_number=2, name='Ep 2')
        mock_providers.return_value = {}

        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=888,
            season_number=1,
            episode_number=1,
            status='watched',
            watched_at='2026-08-01T10:00:00Z',
        )
        response = self.client.get('/api/media/tv/888/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['user_status']['status'], 'watching')

        self.client.post('/api/tracking/shows/drop/', {'tmdb_id': 888})
        response = self.client.get('/api/media/tv/888/')
        self.assertEqual(response.data['user_status']['status'], 'dropped')
        self.assertIn('status_changed_at', response.data['user_status'])

    @patch('media.views.tmdb.sync_movie')
    def test_refresh_movie_metadata_requires_auth(self, mock_sync_movie):
        anon = APIClient()
        response = anon.post('/api/media/movies/550/refresh/', {}, format='json')
        self.assertEqual(response.status_code, 401)
        mock_sync_movie.assert_not_called()

    @patch('media.views.tmdb.sync_tv_show')
    def test_refresh_tv_metadata_requires_auth(self, mock_sync_tv_show):
        anon = APIClient()
        response = anon.post('/api/media/tv/1399/refresh/', {}, format='json')
        self.assertEqual(response.status_code, 401)
        mock_sync_tv_show.assert_not_called()

    @patch('media.views.tmdb.sync_movie')
    def test_refresh_movie_metadata_updates_and_returns_timestamp(self, mock_sync_movie):
        movie = Movie.objects.create(tmdb_id=550, title='Fight Club')
        movie.title = 'Fight Club Updated'
        mock_sync_movie.return_value = movie

        response = self.client.post('/api/media/movies/550/refresh/', {}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['tmdb_id'], 550)
        self.assertIn('metadata_updated_at', response.data)
        mock_sync_movie.assert_called_once_with(550)

    @patch('media.views.tmdb.sync_season')
    @patch('media.views.tmdb.sync_tv_show')
    def test_refresh_tv_metadata_updates_show_and_seasons(self, mock_sync_tv_show, mock_sync_season):
        show = TVShow.objects.create(tmdb_id=1399, name='Game of Thrones', number_of_seasons=2, number_of_episodes=10)
        show.seasons.create(tmdb_id=139900, season_number=0, name='Specials')
        mock_sync_tv_show.return_value = show

        response = self.client.post('/api/media/tv/1399/refresh/', {}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['tmdb_id'], 1399)
        self.assertIn('metadata_updated_at', response.data)
        mock_sync_tv_show.assert_called_once_with(1399)
        self.assertEqual(mock_sync_season.call_count, 3)

    def test_movie_and_tv_detail_include_metadata_updated_at(self):
        Movie.objects.create(tmdb_id=777, title='Movie Detail')
        show = TVShow.objects.create(tmdb_id=888, name='Show Detail', number_of_seasons=1, number_of_episodes=2)
        show.seasons.create(tmdb_id=8881, season_number=1, name='Season 1')

        movie_response = self.client.get('/api/media/movies/777/')
        tv_response = self.client.get('/api/media/tv/888/')

        self.assertEqual(movie_response.status_code, 200)
        self.assertEqual(tv_response.status_code, 200)
        self.assertIn('metadata_updated_at', movie_response.data)
        self.assertIn('metadata_updated_at', tv_response.data)

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from tracking.models import Rating, UserMediaStatus, WatchEntry

from media.models import EpisodeCredit, Genre, Movie, TVShow
from media.tmdb import tmdb

User = get_user_model()


class MediaTests(TestCase):
    @staticmethod
    def _fake_tmdb_get(endpoint, params=None, **kwargs):
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
                'episode_run_time': [57],
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
                        'episode_type': 'finale',
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

    def test_tv_detail_includes_episode_runtime(self):
        response = self.client.get('/api/media/tv/1399/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['episode_runtime'], 57)

    def test_search(self):
        response = self.client.get('/api/media/search/?q=inception')
        self.assertEqual(response.status_code, 200)

    def test_trending(self):
        response = self.client.get('/api/media/trending/')
        self.assertEqual(response.status_code, 200)

    def test_genres_list_returns_sorted_genres(self):
        Genre.objects.create(tmdb_id=1002, name='Thriller')
        Genre.objects.create(tmdb_id=1001, name='Action')

        response = self.client.get('/api/media/genres/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['name'] for row in response.data], ['Action', 'Thriller'])

    def test_season_detail(self):
        response = self.client.get('/api/media/tv/1399/seasons/1/')
        self.assertEqual(response.status_code, 200)

    def test_season_detail_includes_episode_type(self):
        response = self.client.get('/api/media/tv/1399/seasons/1/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['episodes'][0]['episode_type'], 'finale')

    def test_episode_detail(self):
        response = self.client.get('/api/media/tv/1399/seasons/1/episodes/1/credits/')
        self.assertEqual(response.status_code, 200)

    def test_sync_tv_show_persists_episode_type(self):
        tmdb.sync_tv_show(1399)
        show = TVShow.objects.get(tmdb_id=1399)
        season = show.seasons.get(season_number=1)
        episode = season.episodes.get(episode_number=1)
        self.assertEqual(episode.episode_type, 'finale')

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
        UserMediaStatus.objects.create(user=self.user, media_type='movie', tmdb_id=101, status='plan_to_watch')
        WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=102, watched_at='2026-08-01T10:00:00Z')
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
        UserMediaStatus.objects.create(user=self.user, media_type='movie', tmdb_id=201, status='plan_to_watch')
        UserMediaStatus.objects.create(user=self.user, media_type='tv', tmdb_id=202, status='plan_to_watch')

        response = self.client.get('/api/media/search/?q=test&type=multi')
        self.assertEqual(response.status_code, 200)
        results = response.data['results']
        movie_entry = next(item for item in results if item['id'] == 201)
        tv_entry = next(item for item in results if item['id'] == 202)
        person_entry = next(item for item in results if item['id'] == 203)
        self.assertEqual(movie_entry['user_status']['status'], 'plan_to_watch')
        self.assertEqual(tv_entry['user_status']['status'], 'plan_to_watch')
        self.assertNotIn('user_status', person_entry)

    @patch('media.views.tmdb.search_multi')
    def test_search_multi_normalizes_tv_first_air_date_to_release_date(self, mock_search_multi):
        mock_search_multi.return_value = {
            'results': [
                {'id': 202, 'media_type': 'tv', 'name': 'Show', 'first_air_date': '2020-01-15'},
            ],
            'page': 1,
            'total_pages': 1,
            'total_results': 1,
        }

        response = self.client.get('/api/media/search/?q=test&type=multi')
        self.assertEqual(response.status_code, 200)
        result = response.data['results'][0]
        self.assertEqual(result['first_air_date'], '2020-01-15')
        self.assertEqual(result['release_date'], '2020-01-15')

    @patch('media.views.tmdb.find_by_external_id')
    @patch('media.views.tmdb.get_tv_show')
    @patch('media.views.tmdb.get_movie')
    def test_search_prefixed_id_merges_dedupes_and_annotates(self, mock_get_movie, mock_get_tv, mock_find_by_external_id):
        mock_get_movie.return_value = {
            'id': 550,
            'title': 'Fight Club',
            'release_date': '1999-10-15',
            'poster_path': '/movie.jpg',
        }
        mock_get_tv.return_value = {
            'id': 550,
            'name': 'Show 550',
            'first_air_date': '2019-01-01',
            'poster_path': '/show.jpg',
        }

        def fake_find(external_id, external_source):
            if external_source == 'imdb_id':
                return {
                    'movie_results': [
                        {'id': 550, 'title': 'Fight Club', 'media_type': 'movie'},
                        {'id': 777, 'title': 'Seven Seven Seven', 'media_type': 'movie'},
                    ],
                    'tv_results': [
                        {'id': 550, 'name': 'Show 550', 'media_type': 'tv'},
                    ],
                }
            return {'movie_results': [], 'tv_results': []}

        mock_find_by_external_id.side_effect = fake_find
        UserMediaStatus.objects.create(user=self.user, media_type='movie', tmdb_id=550, status='plan_to_watch')
        UserMediaStatus.objects.create(user=self.user, media_type='tv', tmdb_id=550, status='plan_to_watch')

        response = self.client.get('/api/media/search/?q=%23550&type=multi')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total_results'], 3)

        results = response.data['results']
        keys = {(row['media_type'], row['id']) for row in results}
        self.assertEqual(keys, {('movie', 550), ('tv', 550), ('movie', 777)})

        movie_550 = next(row for row in results if row['media_type'] == 'movie' and row['id'] == 550)
        tv_550 = next(row for row in results if row['media_type'] == 'tv' and row['id'] == 550)
        self.assertEqual(movie_550['user_status']['status'], 'plan_to_watch')
        self.assertEqual(tv_550['user_status']['status'], 'plan_to_watch')

    @patch('media.views.tmdb.find_by_external_id')
    def test_search_prefixed_id_applies_scope_filter(self, mock_find_by_external_id):
        mock_find_by_external_id.return_value = {
            'movie_results': [
                {'id': 10, 'title': 'Ten', 'media_type': 'movie'},
            ],
            'tv_results': [
                {'id': 20, 'name': 'Twenty', 'media_type': 'tv'},
            ],
        }

        movies_response = self.client.get('/api/media/search/?q=%23tt0111161&type=movie')
        self.assertEqual(movies_response.status_code, 200)
        self.assertEqual(len(movies_response.data['results']), 1)
        self.assertEqual(movies_response.data['results'][0]['media_type'], 'movie')

        tv_response = self.client.get('/api/media/search/?q=%23tt0111161&type=tv')
        self.assertEqual(tv_response.status_code, 200)
        self.assertEqual(len(tv_response.data['results']), 1)
        self.assertEqual(tv_response.data['results'][0]['media_type'], 'tv')

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

        # Only specials watched -> show status should remain unknown
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=303,
            season_number=0,
            episode_number=1,
            watched_at='2026-08-01T10:00:00Z',
        )

        response = self.client.get('/api/media/popular/?type=tv')
        self.assertEqual(response.status_code, 200)
        status_payload = response.data['results'][0]['user_status']
        self.assertIsNone(status_payload['status'])
        self.assertEqual(status_payload['progress']['total_episodes'], 0)
        self.assertEqual(status_payload['progress']['watched_episodes'], 0)

        # Watch one non-special -> watching
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=303,
            season_number=1,
            episode_number=1,
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
            watched_at='2026-08-03T10:00:00Z',
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=303,
            season_number=2,
            episode_number=1,
            watched_at='2026-08-04T10:00:00Z',
        )
        response = self.client.get('/api/media/popular/?type=tv')
        self.assertEqual(response.data['results'][0]['user_status']['status'], 'watched')

    def test_season_detail_includes_season_zero_own_progress(self):
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
            watched_at='2026-08-01T10:00:00Z',
        )

        response = self.client.get('/api/media/tv/404/seasons/0/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['user_status']['status'], 'watching')
        self.assertEqual(response.data['user_status']['progress']['watched_episodes'], 1)
        self.assertEqual(response.data['user_status']['progress']['total_episodes'], 2)

    @patch('media.views.tmdb.sync_season')
    def test_season_detail_uses_db_first_when_season_exists(self, mock_sync_season):
        show = TVShow.objects.create(tmdb_id=505, name='Show DB First', number_of_seasons=1, number_of_episodes=1)
        season = show.seasons.create(tmdb_id=5050, season_number=1, name='Season 1')
        season.episodes.create(tmdb_id=50501, episode_number=1, name='Existing Episode')

        response = self.client.get('/api/media/tv/505/seasons/1/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['season_number'], 1)
        self.assertEqual(response.data['episodes'][0]['name'], 'Existing Episode')
        mock_sync_season.assert_not_called()

    @patch('media.views.tmdb.sync_episode_credits')
    def test_episode_credits_uses_db_first_when_present(self, mock_sync_episode_credits):
        show = TVShow.objects.create(tmdb_id=606, name='Show Credits', number_of_seasons=1, number_of_episodes=1)
        season = show.seasons.create(tmdb_id=6060, season_number=1, name='Season 1')
        episode = season.episodes.create(tmdb_id=60601, episode_number=1, name='Episode 1')
        EpisodeCredit.objects.create(
            episode=episode,
            cast=[{'name': 'DB Cast Member'}],
            crew=[{'name': 'DB Crew Member', 'job': 'Director'}],
            guest_stars=[{'name': 'DB Guest'}],
        )

        response = self.client.get('/api/media/tv/606/seasons/1/episodes/1/credits/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['cast'][0]['name'], 'DB Cast Member')
        self.assertEqual(response.data['crew'][0]['name'], 'DB Crew Member')
        self.assertEqual(response.data['guest_stars'][0]['name'], 'DB Guest')
        mock_sync_episode_credits.assert_not_called()

    def test_episode_credits_fallback_syncs_and_persists(self):
        show = TVShow.objects.create(tmdb_id=1399, name='Game of Thrones', number_of_seasons=1, number_of_episodes=1)
        season = show.seasons.create(tmdb_id=139901, season_number=1, name='Season 1')
        season.episodes.create(tmdb_id=13990101, episode_number=1, name='Winter Is Coming')

        response = self.client.get('/api/media/tv/1399/seasons/1/episodes/1/credits/')

        self.assertEqual(response.status_code, 200)
        self.assertIn('cast', response.data)
        self.assertIn('crew', response.data)
        self.assertIn('guest_stars', response.data)
        self.assertTrue(
            EpisodeCredit.objects.filter(
                episode__season__show__tmdb_id=1399,
                episode__season__season_number=1,
                episode__episode_number=1,
            ).exists()
        )

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
        UserMediaStatus.objects.create(user=self.user, media_type='movie', tmdb_id=777, status='plan_to_watch')
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
        mock_sync_movie.assert_called_once_with(550, use_cache=False)

    @patch('media.views.sync_show_episode_credits')
    @patch('media.views.tmdb.sync_tv_show')
    def test_refresh_tv_metadata_updates_show_and_seasons(self, mock_sync_tv_show, mock_sync_credits_task):
        show = TVShow.objects.create(tmdb_id=1399, name='Game of Thrones', number_of_seasons=2, number_of_episodes=10)
        show.seasons.create(tmdb_id=139900, season_number=0, name='Specials')
        mock_sync_tv_show.return_value = show

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/media/tv/1399/refresh/', {}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['tmdb_id'], 1399)
        self.assertIn('metadata_updated_at', response.data)
        mock_sync_tv_show.assert_called_once_with(
            1399,
            user_id=self.user.id,
            sync_credits=False,
            use_cache=False,
        )
        mock_sync_credits_task.delay.assert_called_once_with(1399)

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

    @patch('media.tmdb.tmdb.sync_season')
    @patch('media.tmdb.tmdb.get_tv_show')
    def test_sync_tv_show_always_syncs_all_returned_seasons(self, mock_get_tv_show, mock_sync_season):
        mock_get_tv_show.return_value = {
            'id': 555,
            'name': 'Complete Sync Show',
            'overview': 'Complete metadata sync test',
            'first_air_date': '2020-01-01',
            'number_of_seasons': 2,
            'number_of_episodes': 16,
            'vote_average': 8.2,
            'vote_count': 100,
            'original_language': 'en',
            'status': 'Returning Series',
            'networks': [],
            'episode_run_time': [50],
            'genres': [],
            'seasons': [
                {'season_number': 0},
                {'season_number': 1},
                {'season_number': 2},
            ],
        }

        show = tmdb.sync_tv_show(555)

        self.assertEqual(show.tmdb_id, 555)
        self.assertEqual(mock_sync_season.call_count, 3)
        synced_seasons = sorted(call.args[1] for call in mock_sync_season.call_args_list)
        self.assertEqual(synced_seasons, [0, 1, 2])

    @patch('tracking.status_sync.refresh_all_statuses_for_show')
    @patch('media.tmdb.tmdb.sync_season')
    @patch('media.tmdb.tmdb.get_tv_show')
    def test_sync_tv_show_refreshes_all_statuses_with_user(self, mock_get_tv_show, mock_sync_season, mock_refresh_statuses):
        mock_get_tv_show.return_value = {
            'id': 556,
            'name': 'Status Sync Show',
            'overview': 'status refresh test',
            'first_air_date': '2020-01-01',
            'number_of_seasons': 1,
            'number_of_episodes': 8,
            'vote_average': 7.2,
            'vote_count': 50,
            'original_language': 'en',
            'status': 'Returning Series',
            'networks': [],
            'episode_run_time': [45],
            'genres': [],
            'seasons': [{'season_number': 1}],
        }

        show = tmdb.sync_tv_show(556, user_id=self.user.id)

        self.assertEqual(show.tmdb_id, 556)
        mock_sync_season.assert_called_once_with(show, 1, sync_episode_credits=True, use_cache=True)
        mock_refresh_statuses.assert_called_once_with(556, current_user_id=self.user.id)

    @patch('media.tmdb.tmdb.sync_episode_credits')
    @patch('media.tmdb.tmdb.get_season')
    def test_sync_season_refreshes_episode_credits_after_upsert(self, mock_get_season, mock_sync_episode_credits):
        show = TVShow.objects.create(tmdb_id=4242, name='Credits Show', number_of_seasons=1, number_of_episodes=1)
        mock_get_season.return_value = {
            'id': 424201,
            'season_number': 1,
            'name': 'Season 1',
            'air_date': '2024-01-01',
            'episode_count': 1,
            'episodes': [
                {
                    'id': 424211,
                    'episode_number': 1,
                    'name': 'Episode 1',
                    'air_date': '2024-01-02',
                    'runtime': 42,
                }
            ],
        }

        tmdb.sync_season(show, 1)

        mock_sync_episode_credits.assert_called_once_with(4242, 1, 1, show=show, use_cache=True)


class TMDBUseCacheTests(TestCase):
    def test_get_without_cache_skips_read_and_overwrites_cached_entry(self):
        payload = {'id': 550, 'title': 'Fresh Movie'}
        mock_response = MagicMock()
        mock_response.json.return_value = payload

        redis_mock = MagicMock()
        redis_mock.get.return_value = json.dumps({'title': 'Stale Movie'})

        with (
            patch('media.tmdb.requests.get', return_value=mock_response),
            patch.object(tmdb, '_get_redis', return_value=redis_mock),
        ):
            result = tmdb._get('/movie/550', {'append_to_response': 'credits,videos'}, use_cache=False)

        self.assertEqual(result, payload)
        redis_mock.get.assert_not_called()

        expected_key = 'tmdb:/movie/550:' + json.dumps({'append_to_response': 'credits,videos'}, sort_keys=True)
        redis_mock.set.assert_called_once_with(expected_key, json.dumps(payload), ex=tmdb.CACHE_TTL)

    def test_get_with_cache_returns_cached_payload_without_network_call(self):
        cached_payload = {'id': 550, 'title': 'Cached Movie'}

        redis_mock = MagicMock()
        redis_mock.get.return_value = json.dumps(cached_payload)

        with (
            patch('media.tmdb.requests.get') as mock_requests_get,
            patch.object(tmdb, '_get_redis', return_value=redis_mock),
        ):
            result = tmdb._get('/movie/550', {'append_to_response': 'credits,videos'}, use_cache=True)

        self.assertEqual(result, cached_payload)
        mock_requests_get.assert_not_called()
        redis_mock.set.assert_not_called()

    @patch('tracking.status_sync.refresh_all_statuses_for_show')
    @patch('media.tmdb.tmdb.sync_season')
    @patch('media.tmdb.tmdb.get_tv_show')
    def test_sync_tv_show_propagates_use_cache_false(self, mock_get_tv_show, mock_sync_season, mock_refresh_statuses):
        mock_get_tv_show.return_value = {
            'id': 557,
            'name': 'No Cache Show',
            'overview': 'cache bypass test',
            'first_air_date': '2020-01-01',
            'number_of_seasons': 1,
            'number_of_episodes': 4,
            'vote_average': 6.5,
            'vote_count': 20,
            'original_language': 'en',
            'status': 'Returning Series',
            'networks': [],
            'episode_run_time': [40],
            'genres': [],
            'seasons': [{'season_number': 1}],
        }

        show = tmdb.sync_tv_show(557, use_cache=False)

        self.assertEqual(show.tmdb_id, 557)
        mock_get_tv_show.assert_called_once_with(557, use_cache=False)
        mock_sync_season.assert_called_once_with(show, 1, sync_episode_credits=True, use_cache=False)

    @patch('media.tmdb.tmdb.get_movie')
    def test_sync_movie_propagates_use_cache_false(self, mock_get_movie):
        mock_get_movie.return_value = {
            'id': 551,
            'title': 'No Cache Movie',
            'overview': 'cache bypass test',
            'release_date': '2020-01-01',
            'genres': [],
        }

        movie = tmdb.sync_movie(551, use_cache=False)

        self.assertEqual(movie.tmdb_id, 551)
        mock_get_movie.assert_called_once_with(551, use_cache=False)

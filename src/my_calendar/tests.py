from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from media.models import Episode, Movie, Season, TVShow
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from tracking.models import UserMediaStatus, WatchEntry

User = get_user_model()


class CalendarTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='caluser', email='cal@example.com', password='testpass123')
        self.client = APIClient()
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def test_shows_calendar_endpoint(self):
        show = TVShow.objects.create(tmdb_id=200, name='Calendar Show')
        season = Season.objects.create(show=show, tmdb_id=201, season_number=1, name='Season 1')
        Episode.objects.create(
            season=season,
            tmdb_id=202,
            episode_number=1,
            name='Pilot',
            air_date=timezone.localdate() + timedelta(days=1),
        )

        response = self.client.get('/api/calendar/shows/?days=7')
        self.assertEqual(response.status_code, 200)
        self.assertIn('results', response.data)

    def test_shows_calendar_requires_auth(self):
        anon = APIClient()
        response = anon.get('/api/calendar/shows/?days=7')
        self.assertEqual(response.status_code, 401)

    def test_movies_calendar_endpoint(self):
        Movie.objects.create(
            tmdb_id=300,
            title='Calendar Movie',
            release_date=timezone.localdate() + timedelta(days=2),
        )
        response = self.client.get('/api/calendar/movies/?days=7')
        self.assertEqual(response.status_code, 200)
        self.assertIn('results', response.data)

    def test_movies_calendar_requires_auth(self):
        anon = APIClient()
        response = anon.get('/api/calendar/movies/?days=7')
        self.assertEqual(response.status_code, 401)

    def test_my_calendar_includes_watchlist_movies(self):
        movie = Movie.objects.create(
            tmdb_id=301,
            title='My Watchlist Movie',
            release_date=timezone.localdate() + timedelta(days=3),
        )
        UserMediaStatus.objects.create(user=self.user, media_type='movie', tmdb_id=movie.tmdb_id, status='plan_to_watch')

        response = self.client.get('/api/calendar/my/?days=30')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['kind'], 'movie')
        self.assertEqual(response.data['results'][0]['tmdb_id'], movie.tmdb_id)

    def test_my_calendar_includes_watched_show_episodes(self):
        watched_show = TVShow.objects.create(tmdb_id=401, name='Watched Show')
        watched_season = Season.objects.create(show=watched_show, tmdb_id=402, season_number=1, name='Season 1')
        Episode.objects.create(
            season=watched_season,
            tmdb_id=403,
            episode_number=1,
            name='Watched Episode',
            air_date=timezone.localdate() + timedelta(days=4),
        )

        dropped_show = TVShow.objects.create(tmdb_id=501, name='Dropped Show')
        dropped_season = Season.objects.create(show=dropped_show, tmdb_id=502, season_number=1, name='Season 1')
        Episode.objects.create(
            season=dropped_season,
            tmdb_id=503,
            episode_number=1,
            name='Dropped Episode',
            air_date=timezone.localdate() + timedelta(days=5),
        )

        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=watched_show.tmdb_id,
            season_number=1,
            episode_number=1,
        )
        UserMediaStatus.objects.create(
            user=self.user,
            media_type='tv',
            tmdb_id=dropped_show.tmdb_id,
            status='dropped',
            watched_episodes=1,
            total_episodes=1,
            progress_percent=100,
            dropped_at=timezone.now(),
            status_changed_at=timezone.now(),
        )

        response = self.client.get('/api/calendar/my/?days=30')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['kind'], 'episode')
        self.assertEqual(response.data['results'][0]['tmdb_id'], watched_show.tmdb_id)

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone

from tracking.models import (
    UserMediaStatus,
    WatchEntry,
)

User = get_user_model()
from .base import BaseTestCase


class RecommendationsTests(BaseTestCase):
    @patch('media.tmdb.tmdb.get_popular_movies')
    @patch('media.tmdb.tmdb.get_popular_tv')
    def test_recommendations_exclude_watched_and_watchlist(self, mock_tv, mock_movies):
        WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=10)
        UserMediaStatus.objects.create(user=self.user, media_type='tv', tmdb_id=20, status='plan_to_watch', status_changed_at=timezone.now())

        mock_movies.return_value = {'results': [{'id': 10}, {'id': 11}]}
        mock_tv.return_value = {'results': [{'id': 20}, {'id': 21}]}

        response = self.client.get('/api/tracking/recommendations/')
        self.assertEqual(response.status_code, 200)
        movie_ids = [m['id'] for m in response.data['movies']]
        tv_ids = [t['id'] for t in response.data['tv']]
        self.assertNotIn(10, movie_ids)
        self.assertNotIn(20, tv_ids)


    @patch('media.tmdb.tmdb.get_popular_movies', return_value={'results': []})
    @patch('media.tmdb.tmdb.get_popular_tv', return_value={'results': []})
    def test_recommendations_flag_insufficient_history_below_three_entries(self, mock_tv, mock_movies):
        for episode_number in (1, 2):
            WatchEntry.objects.create(user=self.user, media_type='episode', tmdb_id=30, season_number=1, episode_number=episode_number)
        self.assertTrue(self.client.get('/api/tracking/recommendations/').data['insufficient_history'])

        WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=31)
        self.assertFalse(self.client.get('/api/tracking/recommendations/').data['insufficient_history'])

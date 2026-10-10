from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone

from tracking.cache import cache
from tracking.models import (
    Rating,
    WatchEntry,
)

User = get_user_model()
from .base import BaseTestCase


class UserStatsTests(BaseTestCase):
    def test_stats_endpoint(self):
        response = self.client.get('/api/tracking/stats/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('movies_watched', response.data)
        self.assertIn('episodes_watched', response.data)

    def test_stats_with_watched_movie(self):
        WatchEntry.objects.create(
            user=self.user, media_type='movie', tmdb_id=123,
            watched_at=timezone.now()
        )
        response = self.client.get('/api/tracking/stats/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['movies_watched'], 1)

    def test_stats_counts_all_distinct_watched_movies(self):
        WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=123, watched_at=timezone.now())
        WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=456, watched_at=timezone.now())

        response = self.client.get('/api/tracking/stats/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['movies_watched'], 2)

    def test_stats_cache_hit_does_not_recompute(self):

        cache.invalidate_user_stats(self.user.id)
        with patch.object(cache, '_compute_user_stats', wraps=cache._compute_user_stats) as compute:
            first = cache.get_user_stats(self.user.id)
            second = cache.get_user_stats(self.user.id)

        self.assertEqual(first, second)
        compute.assert_called_once_with(self.user.id)

    def test_recent_activity_includes_rating_when_available(self):
        watched_at = timezone.now()
        WatchEntry.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=999,
            watched_at=watched_at,
        )
        Rating.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=999,
            score=8,
        )

        response = self.client.get('/api/tracking/stats/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['recent_activity'])
        first = response.data['recent_activity'][0]
        self.assertEqual(first['tmdb_id'], 999)
        self.assertEqual(first['rating'], 8)

    def test_stats_cache_invalidated_on_history_delete(self):
        entry = WatchEntry.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=321,
            watched_at=timezone.now(),
        )

        warm = self.client.get('/api/tracking/stats/')
        self.assertEqual(warm.status_code, 200)
        self.assertEqual(warm.data['movies_watched'], 1)

        delete_resp = self.client.delete(f'/api/tracking/history/{entry.id}/')
        self.assertEqual(delete_resp.status_code, 204)

        after = self.client.get('/api/tracking/stats/')
        self.assertEqual(after.status_code, 200)
        self.assertEqual(after.data['movies_watched'], 0)

    def test_stats_cache_invalidated_on_episode_history_delete(self):
        entry = WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=654,
            season_number=1,
            episode_number=1,
            watched_at=timezone.now(),
        )

        warm = self.client.get('/api/tracking/stats/')
        self.assertEqual(warm.status_code, 200)
        self.assertEqual(warm.data['shows_watching'], 1)

        delete_resp = self.client.delete(f'/api/tracking/history/{entry.id}/')
        self.assertEqual(delete_resp.status_code, 204)

        after = self.client.get('/api/tracking/stats/')
        self.assertEqual(after.status_code, 200)
        self.assertEqual(after.data['shows_watching'], 0)

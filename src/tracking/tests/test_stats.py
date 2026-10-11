from django.contrib.auth import get_user_model
from django.utils import timezone

from media.models import Episode, Movie, Season, TVShow
from tracking.models import (
    Rating,
    UserMediaStatus,
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

    def test_stats_watch_time_zero_without_history(self):
        response = self.client.get('/api/tracking/stats/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['watch_time_minutes'], 0)

    def test_stats_watch_time_sums_movie_runtimes(self):
        Movie.objects.create(tmdb_id=123, title='Long Film', runtime=136)
        Movie.objects.create(tmdb_id=456, title='Short Film', runtime=90)
        WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=123, watched_at=timezone.now())
        WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=456, watched_at=timezone.now())
        # Unknown titles with no local record contribute 0.
        WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=999, watched_at=timezone.now())

        response = self.client.get('/api/tracking/stats/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['watch_time_minutes'], 226)

    def test_stats_watch_time_episodes_prefer_own_runtime_then_show_fallback(self):
        show = TVShow.objects.create(tmdb_id=124, name='Runtime Show', episode_runtime=45)
        season = Season.objects.create(show=show, tmdb_id=1241, season_number=1, name='Season 1')
        Episode.objects.create(season=season, tmdb_id=12411, episode_number=1, name='Long One', runtime=60)
        Episode.objects.create(season=season, tmdb_id=12412, episode_number=2, name='Fallback One')
        Episode.objects.create(season=season, tmdb_id=12413, episode_number=3, name='Unwatched One', runtime=60)
        for episode_number in (1, 2):
            WatchEntry.objects.create(
                user=self.user, media_type='episode', tmdb_id=124,
                season_number=1, episode_number=episode_number, watched_at=timezone.now(),
            )

        response = self.client.get('/api/tracking/stats/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['watch_time_minutes'], 105)

    def test_stats_watch_time_ignores_episodes_without_any_runtime(self):
        show = TVShow.objects.create(tmdb_id=125, name='Unknown Runtimes')
        season = Season.objects.create(show=show, tmdb_id=1251, season_number=1, name='Season 1')
        Episode.objects.create(season=season, tmdb_id=12511, episode_number=1, name='Mystery')
        WatchEntry.objects.create(
            user=self.user, media_type='episode', tmdb_id=125,
            season_number=1, episode_number=1, watched_at=timezone.now(),
        )
        # Entry for a season never synced locally contributes 0.
        WatchEntry.objects.create(
            user=self.user, media_type='episode', tmdb_id=125,
            season_number=9, episode_number=1, watched_at=timezone.now(),
        )

        response = self.client.get('/api/tracking/stats/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['watch_time_minutes'], 0)

    def test_stats_watching_excludes_watched_shows(self):
        for tmdb_id in (124, 125):
            WatchEntry.objects.create(
                user=self.user, media_type='episode', tmdb_id=tmdb_id,
                season_number=1, episode_number=1, watched_at=timezone.now(),
            )
        UserMediaStatus.objects.filter(user=self.user, media_type='tv', tmdb_id=124).update(status='watched')

        response = self.client.get('/api/tracking/stats/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['shows_watching'], 1)
        self.assertEqual(response.data['shows_watched'], 1)

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

        response = self.client.get('/api/tracking/activity/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data)
        first = response.data[0]
        self.assertEqual(first['tmdb_id'], 999)
        self.assertEqual(first['rating'], 8)

    def test_stats_returns_only_card_values(self):
        WatchEntry.objects.create(
            user=self.user, media_type='movie', tmdb_id=123, watched_at=timezone.now()
        )

        response = self.client.get('/api/tracking/stats/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.data.keys()),
            {'movies_watched', 'shows_watching', 'shows_watched', 'episodes_watched', 'watch_time_minutes', 'average_rating'},
        )

    def test_stats_reflect_history_delete(self):
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

    def test_stats_reflect_episode_history_delete(self):
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

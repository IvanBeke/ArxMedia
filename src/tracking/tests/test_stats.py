import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from media.models import Episode, Movie, Season, TVShow
from tracking.models import (
    Rating,
    UserMediaStatus,
    WatchEntry,
)

User = get_user_model()


pytestmark = pytest.mark.django_db

class UserStatsTests:
    def test_stats_endpoint(self, user, auth_client, user2, tmdb_noop):
        response = auth_client.get('/api/tracking/stats/')
        assert response.status_code == 200
        assert 'movies_watched' in response.data
        assert 'episodes_watched' in response.data

    def test_stats_with_watched_movie(self, user, auth_client, user2, tmdb_noop):
        WatchEntry.objects.create(
            user=user, media_type='movie', tmdb_id=123,
            watched_at=timezone.now()
        )
        response = auth_client.get('/api/tracking/stats/')
        assert response.status_code == 200
        assert response.data['movies_watched'] == 1

    def test_stats_counts_all_distinct_watched_movies(self, user, auth_client, user2, tmdb_noop):
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=123, watched_at=timezone.now())
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=456, watched_at=timezone.now())

        response = auth_client.get('/api/tracking/stats/')

        assert response.status_code == 200
        assert response.data['movies_watched'] == 2

    def test_stats_watch_time_zero_without_history(self, user, auth_client, user2, tmdb_noop):
        response = auth_client.get('/api/tracking/stats/')

        assert response.status_code == 200
        assert response.data['watch_time_minutes'] == 0

    def test_stats_watch_time_sums_movie_runtimes(self, user, auth_client, user2, tmdb_noop):
        Movie.objects.create(tmdb_id=123, title='Long Film', runtime=136)
        Movie.objects.create(tmdb_id=456, title='Short Film', runtime=90)
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=123, watched_at=timezone.now())
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=456, watched_at=timezone.now())
        # Unknown titles with no local record contribute 0.
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=999, watched_at=timezone.now())

        response = auth_client.get('/api/tracking/stats/')

        assert response.status_code == 200
        assert response.data['watch_time_minutes'] == 226

    def test_stats_watch_time_episodes_prefer_own_runtime_then_show_fallback(self, user, auth_client, user2, tmdb_noop):
        show = TVShow.objects.create(tmdb_id=124, name='Runtime Show', episode_runtime=45)
        season = Season.objects.create(show=show, tmdb_id=1241, season_number=1, name='Season 1')
        Episode.objects.create(season=season, tmdb_id=12411, episode_number=1, name='Long One', runtime=60)
        Episode.objects.create(season=season, tmdb_id=12412, episode_number=2, name='Fallback One')
        Episode.objects.create(season=season, tmdb_id=12413, episode_number=3, name='Unwatched One', runtime=60)
        for episode_number in (1, 2):
            WatchEntry.objects.create(
                user=user, media_type='episode', tmdb_id=124,
                season_number=1, episode_number=episode_number, watched_at=timezone.now(),
            )

        response = auth_client.get('/api/tracking/stats/')

        assert response.status_code == 200
        assert response.data['watch_time_minutes'] == 105

    def test_stats_watch_time_ignores_episodes_without_any_runtime(self, user, auth_client, user2, tmdb_noop):
        show = TVShow.objects.create(tmdb_id=125, name='Unknown Runtimes')
        season = Season.objects.create(show=show, tmdb_id=1251, season_number=1, name='Season 1')
        Episode.objects.create(season=season, tmdb_id=12511, episode_number=1, name='Mystery')
        WatchEntry.objects.create(
            user=user, media_type='episode', tmdb_id=125,
            season_number=1, episode_number=1, watched_at=timezone.now(),
        )
        # Entry for a season never synced locally contributes 0.
        WatchEntry.objects.create(
            user=user, media_type='episode', tmdb_id=125,
            season_number=9, episode_number=1, watched_at=timezone.now(),
        )

        response = auth_client.get('/api/tracking/stats/')

        assert response.status_code == 200
        assert response.data['watch_time_minutes'] == 0

    def test_stats_watching_excludes_watched_shows(self, user, auth_client, user2, tmdb_noop):
        for tmdb_id in (124, 125):
            WatchEntry.objects.create(
                user=user, media_type='episode', tmdb_id=tmdb_id,
                season_number=1, episode_number=1, watched_at=timezone.now(),
            )
        UserMediaStatus.objects.filter(user=user, media_type='tv', tmdb_id=124).update(status='watched')

        response = auth_client.get('/api/tracking/stats/')

        assert response.status_code == 200
        assert response.data['shows_watching'] == 1
        assert response.data['shows_watched'] == 1

    def test_recent_activity_includes_rating_when_available(self, user, auth_client, user2, tmdb_noop):
        watched_at = timezone.now()
        WatchEntry.objects.create(
            user=user,
            media_type='movie',
            tmdb_id=999,
            watched_at=watched_at,
        )
        Rating.objects.create(
            user=user,
            media_type='movie',
            tmdb_id=999,
            score=8,
        )

        response = auth_client.get('/api/tracking/activity/')
        assert response.status_code == 200
        assert response.data
        first = response.data[0]
        assert first['tmdb_id'] == 999
        assert first['rating'] == 8

    def test_stats_returns_only_card_values(self, user, auth_client, user2, tmdb_noop):
        WatchEntry.objects.create(
            user=user, media_type='movie', tmdb_id=123, watched_at=timezone.now()
        )

        response = auth_client.get('/api/tracking/stats/')

        assert response.status_code == 200
        assert set(response.data.keys()) == {'movies_watched', 'shows_watching', 'shows_watched', 'episodes_watched', 'watch_time_minutes', 'average_rating'}

    def test_stats_reflect_history_delete(self, user, auth_client, user2, tmdb_noop):
        entry = WatchEntry.objects.create(
            user=user,
            media_type='movie',
            tmdb_id=321,
            watched_at=timezone.now(),
        )

        warm = auth_client.get('/api/tracking/stats/')
        assert warm.status_code == 200
        assert warm.data['movies_watched'] == 1

        delete_resp = auth_client.delete(f'/api/tracking/history/{entry.id}/')
        assert delete_resp.status_code == 204

        after = auth_client.get('/api/tracking/stats/')
        assert after.status_code == 200
        assert after.data['movies_watched'] == 0

    def test_stats_reflect_episode_history_delete(self, user, auth_client, user2, tmdb_noop):
        entry = WatchEntry.objects.create(
            user=user,
            media_type='episode',
            tmdb_id=654,
            season_number=1,
            episode_number=1,
            watched_at=timezone.now(),
        )

        warm = auth_client.get('/api/tracking/stats/')
        assert warm.status_code == 200
        assert warm.data['shows_watching'] == 1

        delete_resp = auth_client.delete(f'/api/tracking/history/{entry.id}/')
        assert delete_resp.status_code == 204

        after = auth_client.get('/api/tracking/stats/')
        assert after.status_code == 200
        assert after.data['shows_watching'] == 0

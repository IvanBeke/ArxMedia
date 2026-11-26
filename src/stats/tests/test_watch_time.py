import pytest
from django.utils import timezone

from media.models import Episode, Movie, Season, TVShow
from tracking.models import WatchEntry

pytestmark = pytest.mark.django_db


class WatchTimeStatsTests:
    def _get(self, client, user):
        response = client.get(f'/api/stats/{user.username}/watch-time/')
        assert response.status_code == 200
        return response.data

    def test_zero_without_history(self, user, auth_client, user2, tmdb_noop):
        assert self._get(auth_client, user) == {'movie_minutes': 0, 'episode_minutes': 0, 'watch_time_minutes': 0}

    def test_sums_movie_runtimes(self, user, auth_client, user2, tmdb_noop):
        Movie.objects.create(tmdb_id=123, title='Long Film', runtime=136)
        Movie.objects.create(tmdb_id=456, title='Short Film', runtime=90)
        for tmdb_id in (123, 456, 999):
            WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=tmdb_id, watched_at=timezone.now())

        data = self._get(auth_client, user)

        # The title with no local record contributes 0.
        assert data['movie_minutes'] == 226
        assert data['watch_time_minutes'] == 226

    def test_episodes_prefer_own_runtime_then_show_fallback(self, user, auth_client, user2, tmdb_noop):
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

        assert self._get(auth_client, user)['episode_minutes'] == 105

    def test_ignores_episodes_without_any_runtime(self, user, auth_client, user2, tmdb_noop):
        show = TVShow.objects.create(tmdb_id=125, name='Unknown Runtimes')
        season = Season.objects.create(show=show, tmdb_id=1251, season_number=1, name='Season 1')
        Episode.objects.create(season=season, tmdb_id=12511, episode_number=1, name='Mystery')
        WatchEntry.objects.create(
            user=user, media_type='episode', tmdb_id=125,
            season_number=1, episode_number=1, watched_at=timezone.now(),
        )
        # An entry for a season never synced locally contributes 0 as well.
        WatchEntry.objects.create(
            user=user, media_type='episode', tmdb_id=125,
            season_number=9, episode_number=1, watched_at=timezone.now(),
        )

        assert self._get(auth_client, user)['episode_minutes'] == 0

    def test_total_adds_movies_and_episodes_of_the_user_only(self, user, auth_client, user2, tmdb_noop):
        Movie.objects.create(tmdb_id=1, title='Film', runtime=100)
        show = TVShow.objects.create(tmdb_id=2, name='Show', episode_runtime=40)
        season = Season.objects.create(show=show, tmdb_id=21, season_number=1, name='Season 1')
        Episode.objects.create(season=season, tmdb_id=211, episode_number=1, name='One')
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=1, watched_at=timezone.now())
        WatchEntry.objects.create(
            user=user, media_type='episode', tmdb_id=2, season_number=1, episode_number=1, watched_at=timezone.now(),
        )
        WatchEntry.objects.create(user=user2, media_type='movie', tmdb_id=1, watched_at=timezone.now())

        data = self._get(auth_client, user)

        assert (data['movie_minutes'], data['episode_minutes'], data['watch_time_minutes']) == (100, 40, 140)

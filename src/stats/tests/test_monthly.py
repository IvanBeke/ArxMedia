import zoneinfo
from datetime import datetime

import pytest
from django.conf import settings
from django.utils import timezone

from media.models import Episode, Movie, Season, TVShow
from tracking.models import WatchEntry

pytestmark = pytest.mark.django_db

TZ = zoneinfo.ZoneInfo(settings.TIME_ZONE)


class MonthlyStatsTests:
    def _get(self, client, user, **params):
        response = client.get(f'/api/stats/{user.username}/monthly/', params)
        assert response.status_code == 200
        return response.data

    def test_defaults_to_the_current_year_with_all_twelve_months_filled(self, user, auth_client, user2, tmdb_noop):
        data = self._get(auth_client, user)

        year = timezone.localdate().year
        assert data['year'] == year
        assert [month['month'] for month in data['months']] == [f'{year}-{number:02d}' for number in range(1, 13)]
        assert all(month['movie_minutes'] == 0 and month['episode_minutes'] == 0 for month in data['months'])

    def test_returns_the_requested_year(self, user, auth_client, user2, tmdb_noop):
        data = self._get(auth_client, user, year=2021)

        assert data['year'] == 2021
        assert data['months'][0]['month'] == '2021-01'
        assert data['months'][-1]['month'] == '2021-12'

    def test_splits_watch_time_by_media_type_and_leaves_out_other_years_and_undated_entries(
        self, user, auth_client, user2, tmdb_noop,
    ):
        Movie.objects.create(tmdb_id=123, title='Long Film', runtime=100)
        Movie.objects.create(tmdb_id=456, title='Other Year Film', runtime=50)
        Movie.objects.create(tmdb_id=789, title='Undated Film', runtime=70)
        show = TVShow.objects.create(tmdb_id=124, name='Runtime Show', episode_runtime=40)
        season = Season.objects.create(show=show, tmdb_id=1241, season_number=1, name='Season 1')
        Episode.objects.create(season=season, tmdb_id=12411, episode_number=1, name='One', runtime=60)
        Episode.objects.create(season=season, tmdb_id=12412, episode_number=2, name='Two')
        in_march = datetime(2025, 3, 10, 20, tzinfo=TZ)
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=123, watched_at=in_march)
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=456, watched_at=datetime(2024, 3, 10, tzinfo=TZ))
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=789, watched_at=None)
        for episode_number in (1, 2):
            WatchEntry.objects.create(
                user=user, media_type='episode', tmdb_id=124,
                season_number=1, episode_number=episode_number, watched_at=in_march,
            )
        WatchEntry.objects.create(user=user2, media_type='movie', tmdb_id=123, watched_at=in_march)

        months = self._get(auth_client, user, year=2025)['months']

        assert months[2] == {'month': '2025-03', 'movie_minutes': 100, 'episode_minutes': 100}
        assert sum(month['movie_minutes'] for month in months) == 100
        assert sum(month['episode_minutes'] for month in months) == 100

    def test_year_boundaries_follow_the_server_timezone(self, user, auth_client, user2, tmdb_noop):
        Movie.objects.create(tmdb_id=1, title='New Year Eve Film', runtime=10)
        Movie.objects.create(tmdb_id=2, title='New Year Film', runtime=20)
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=1, watched_at=datetime(2025, 12, 31, 23, 30, tzinfo=TZ))
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=2, watched_at=datetime(2026, 1, 1, 0, 30, tzinfo=TZ))

        last_year = self._get(auth_client, user, year=2025)['months']
        this_year = self._get(auth_client, user, year=2026)['months']

        assert [month['movie_minutes'] for month in last_year] == [0] * 11 + [10]
        assert [month['movie_minutes'] for month in this_year] == [20] + [0] * 11

    @pytest.mark.parametrize('year', ['abc', '', '-1', '20.5', '1899', '3000'])
    def test_rejects_an_invalid_year(self, year, user, auth_client, user2, tmdb_noop):
        response = auth_client.get(f'/api/stats/{user.username}/monthly/', {'year': year})

        assert response.status_code == 400
        assert 'year' in response.data

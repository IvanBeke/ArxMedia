import zoneinfo
from datetime import datetime

import pytest
from django.conf import settings

from tracking.models import WatchEntry

pytestmark = pytest.mark.django_db


class HabitsStatsTests:
    def _get(self, client, user):
        response = client.get(f'/api/stats/{user.username}/habits/')
        assert response.status_code == 200
        return response.data

    def test_counts_by_weekday_and_hour_per_media_type(self, user, auth_client, user2, tmdb_noop):
        tz = zoneinfo.ZoneInfo(settings.TIME_ZONE)
        monday_evening = datetime(2026, 3, 2, 21, 30, tzinfo=tz)
        sunday_midnight = datetime(2026, 3, 8, 0, 5, tzinfo=tz)
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=1, watched_at=monday_evening)
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=2, watched_at=sunday_midnight)
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=3, watched_at=None)
        for episode_number in (1, 2):
            WatchEntry.objects.create(
                user=user, media_type='episode', tmdb_id=9,
                season_number=1, episode_number=episode_number, watched_at=monday_evening,
            )
        WatchEntry.objects.create(user=user2, media_type='movie', tmdb_id=1, watched_at=monday_evening)

        data = self._get(auth_client, user)

        movies = data['movie']
        assert movies['weekdays'] == [1, 0, 0, 0, 0, 0, 1]
        assert movies['hours'][21] == 1
        assert movies['hours'][0] == 1
        assert sum(movies['hours']) == 2
        episodes = data['episode']
        assert episodes['weekdays'] == [2, 0, 0, 0, 0, 0, 0]
        assert episodes['hours'][21] == 2
        assert len(episodes['hours']) == 24

    def test_empty_without_history(self, user, auth_client, user2, tmdb_noop):
        empty = {'weekdays': [0] * 7, 'hours': [0] * 24}

        assert self._get(auth_client, user) == {'movie': empty, 'episode': empty}

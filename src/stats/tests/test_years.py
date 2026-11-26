import zoneinfo
from datetime import datetime

import pytest
from django.conf import settings
from django.utils import timezone

from tracking.models import WatchEntry

pytestmark = pytest.mark.django_db

TZ = zoneinfo.ZoneInfo(settings.TIME_ZONE)


class YearsStatsTests:
    def _get(self, client, user):
        response = client.get(f'/api/stats/{user.username}/years/')
        assert response.status_code == 200
        return response.data

    def test_without_dated_entries_only_the_current_year_is_known(self, user, auth_client, user2, tmdb_noop):
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=1, watched_at=None)

        assert self._get(auth_client, user) == {'current_year': timezone.localdate().year, 'earliest_year': None}

    def test_earliest_year_is_the_year_of_the_first_dated_entry(self, user, auth_client, user2, tmdb_noop):
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=1, watched_at=datetime(2023, 5, 1, tzinfo=TZ))
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=2, watched_at=datetime(2021, 8, 1, tzinfo=TZ))
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=3, watched_at=None)
        WatchEntry.objects.create(user=user2, media_type='movie', tmdb_id=4, watched_at=datetime(2015, 1, 1, tzinfo=TZ))

        assert self._get(auth_client, user)['earliest_year'] == 2021

    def test_earliest_year_follows_the_server_timezone(self, user, auth_client, user2, tmdb_noop):
        # 00:30 on New Year's Day in the server timezone is still the previous year in UTC.
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=1, watched_at=datetime(2021, 1, 1, 0, 30, tzinfo=TZ))

        assert self._get(auth_client, user)['earliest_year'] == 2021

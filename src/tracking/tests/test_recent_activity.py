import pytest
from django.utils import timezone

from tracking.models import Rating, WatchEntry

pytestmark = pytest.mark.django_db


class RecentActivityTests:
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

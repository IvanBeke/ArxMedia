import pytest
from django.utils import timezone

from tracking.models import WatchEntry

pytestmark = pytest.mark.django_db


class WatchCountStatsTests:
    def _get(self, client, user):
        response = client.get(f'/api/stats/{user.username}/watch-count/')
        assert response.status_code == 200
        return response.data

    def test_zero_without_history(self, user, auth_client, user2, tmdb_noop):
        assert self._get(auth_client, user) == {'movies_watched': 0, 'episodes_watched': 0}

    def test_counts_movies_and_episodes_of_the_user_only(self, user, auth_client, user2, tmdb_noop):
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=123, watched_at=timezone.now())
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=456, watched_at=timezone.now())
        for episode_number in (1, 2, 3):
            WatchEntry.objects.create(
                user=user, media_type='episode', tmdb_id=9,
                season_number=1, episode_number=episode_number, watched_at=timezone.now(),
            )
        WatchEntry.objects.create(user=user2, media_type='movie', tmdb_id=123, watched_at=timezone.now())

        assert self._get(auth_client, user) == {'movies_watched': 2, 'episodes_watched': 3}

    def test_counts_entries_without_a_watch_date_or_synced_media(self, user, auth_client, user2, tmdb_noop):
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=999, watched_at=None)

        assert self._get(auth_client, user)['movies_watched'] == 1

    def test_reflects_history_delete(self, user, auth_client, user2, tmdb_noop):
        entry = WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=321, watched_at=timezone.now())
        assert self._get(auth_client, user)['movies_watched'] == 1

        assert auth_client.delete(f'/api/tracking/history/{entry.id}/').status_code == 204

        assert self._get(auth_client, user)['movies_watched'] == 0

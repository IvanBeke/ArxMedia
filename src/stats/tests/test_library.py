import pytest
from django.utils import timezone

from tracking.models import UserMediaStatus, WatchEntry

pytestmark = pytest.mark.django_db


class LibraryStatsTests:
    def _get(self, client, user):
        response = client.get(f'/api/stats/{user.username}/library/')
        assert response.status_code == 200
        return response.data

    def test_show_statuses_and_watchlist_count(self, user, auth_client, user2, tmdb_noop):
        for tmdb_id, status in ((1, 'watching'), (2, 'watched'), (3, 'watched'), (4, 'dropped'), (5, 'plan_to_watch')):
            UserMediaStatus.objects.create(user=user, media_type='tv', tmdb_id=tmdb_id, status=status)
        UserMediaStatus.objects.set_planning(user, 'movie', 6)
        UserMediaStatus.objects.create(user=user2, media_type='tv', tmdb_id=7, status='watching')

        data = self._get(auth_client, user)

        assert data['show_statuses'] == {'plan_to_watch': 1, 'watching': 1, 'watched': 2, 'dropped': 1}
        assert data['watchlist_count'] == 2

    def test_movie_statuses_and_media_types(self, user, auth_client, user2, tmdb_noop):
        for tmdb_id, status in ((1, 'watched'), (2, 'watched'), (3, 'plan_to_watch'), (4, 'dropped')):
            UserMediaStatus.objects.create(user=user, media_type='movie', tmdb_id=tmdb_id, status=status)
        for tmdb_id, status in ((10, 'watching'), (11, 'watched')):
            UserMediaStatus.objects.create(user=user, media_type='tv', tmdb_id=tmdb_id, status=status)
        UserMediaStatus.objects.create(user=user2, media_type='movie', tmdb_id=5, status='watched')

        data = self._get(auth_client, user)

        assert data['movie_statuses'] == {'plan_to_watch': 1, 'watched': 2, 'dropped': 1}
        assert data['media_types'] == {'movie': 4, 'tv': 2}

    def test_empty_library(self, user, auth_client, user2, tmdb_noop):
        assert self._get(auth_client, user) == {
            'show_statuses': {'plan_to_watch': 0, 'watching': 0, 'watched': 0, 'dropped': 0},
            'movie_statuses': {'plan_to_watch': 0, 'watched': 0, 'dropped': 0},
            'media_types': {'movie': 0, 'tv': 0},
            'watchlist_count': 0,
        }

    def test_watching_excludes_watched_shows(self, user, auth_client, user2, tmdb_noop):
        for tmdb_id in (124, 125):
            WatchEntry.objects.create(
                user=user, media_type='episode', tmdb_id=tmdb_id,
                season_number=1, episode_number=1, watched_at=timezone.now(),
            )
        UserMediaStatus.objects.filter(user=user, media_type='tv', tmdb_id=124).update(status='watched')

        data = self._get(auth_client, user)

        assert data['show_statuses']['watching'] == 1
        assert data['show_statuses']['watched'] == 1

    def test_reflects_episode_history_delete(self, user, auth_client, user2, tmdb_noop):
        entry = WatchEntry.objects.create(
            user=user, media_type='episode', tmdb_id=654,
            season_number=1, episode_number=1, watched_at=timezone.now(),
        )
        assert self._get(auth_client, user)['show_statuses']['watching'] == 1

        assert auth_client.delete(f'/api/tracking/history/{entry.id}/').status_code == 204

        assert self._get(auth_client, user)['show_statuses']['watching'] == 0

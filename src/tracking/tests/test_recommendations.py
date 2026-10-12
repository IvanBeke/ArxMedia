
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from tracking.models import (
    UserMediaStatus,
    WatchEntry,
)

User = get_user_model()


pytestmark = pytest.mark.django_db

class RecommendationsTests:
    def test_recommendations_exclude_watched_and_watchlist(self, mocker, user, auth_client, user2, tmdb_noop):
        mock_tv = mocker.patch('media.tmdb.tmdb.get_popular_tv')
        mock_movies = mocker.patch('media.tmdb.tmdb.get_popular_movies')
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=10)
        UserMediaStatus.objects.create(user=user, media_type='tv', tmdb_id=20, status='plan_to_watch', status_changed_at=timezone.now())

        mock_movies.return_value = {'results': [{'id': 10}, {'id': 11}]}
        mock_tv.return_value = {'results': [{'id': 20}, {'id': 21}]}

        response = auth_client.get('/api/tracking/recommendations/')
        assert response.status_code == 200
        movie_ids = [m['id'] for m in response.data['movies']]
        tv_ids = [t['id'] for t in response.data['tv']]
        assert 10 not in movie_ids
        assert 20 not in tv_ids


    def test_recommendations_flag_insufficient_history_below_three_entries(self, mocker, user, auth_client, user2, tmdb_noop):
        mocker.patch('media.tmdb.tmdb.get_popular_tv', return_value={'results': []})
        mocker.patch('media.tmdb.tmdb.get_popular_movies', return_value={'results': []})
        for episode_number in (1, 2):
            WatchEntry.objects.create(user=user, media_type='episode', tmdb_id=30, season_number=1, episode_number=episode_number)
        assert auth_client.get('/api/tracking/recommendations/').data['insufficient_history']

        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=31)
        assert not auth_client.get('/api/tracking/recommendations/').data['insufficient_history']

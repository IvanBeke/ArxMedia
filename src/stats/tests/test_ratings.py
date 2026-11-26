import pytest

from tracking.models import Rating

pytestmark = pytest.mark.django_db


class RatingStatsTests:
    def _get(self, client, user):
        response = client.get(f'/api/stats/{user.username}/ratings/')
        assert response.status_code == 200
        return response.data

    def test_summary_and_distribution(self, user, auth_client, user2, tmdb_noop):
        for tmdb_id, score in ((1, 10), (2, 7), (3, 7), (4, 2)):
            Rating.objects.create(user=user, media_type='movie', tmdb_id=tmdb_id, score=score)
        Rating.objects.create(user=user2, media_type='movie', tmdb_id=1, score=3)

        data = self._get(auth_client, user)

        assert data == {
            'ratings_count': 4,
            'average_rating': 6.5,
            'rating_distribution': [0, 1, 0, 0, 0, 0, 2, 0, 0, 1],
        }

    def test_average_is_rounded_by_the_database_half_up(self, user, auth_client, user2, tmdb_noop):
        for tmdb_id, score in ((1, 10), (2, 7), (3, 7), (4, 1)):
            Rating.objects.create(user=user, media_type='movie', tmdb_id=tmdb_id, score=score)

        assert self._get(auth_client, user)['average_rating'] == 6.3

    def test_shows_and_movies_are_counted_together(self, user, auth_client, user2, tmdb_noop):
        Rating.objects.create(user=user, media_type='movie', tmdb_id=1, score=4)
        Rating.objects.create(user=user, media_type='tv', tmdb_id=1, score=6)

        data = self._get(auth_client, user)

        assert data['ratings_count'] == 2
        assert data['average_rating'] == 5.0

    def test_without_ratings(self, user, auth_client, user2, tmdb_noop):
        assert self._get(auth_client, user) == {
            'ratings_count': 0,
            'average_rating': None,
            'rating_distribution': [0] * 10,
        }

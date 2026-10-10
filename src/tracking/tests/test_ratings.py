
from django.contrib.auth import get_user_model
from django.utils import timezone

from tracking.models import (
    Rating,
    UserMediaStatus,
    WatchEntry,
)

User = get_user_model()
from .base import BaseTestCase


class RatingTests(BaseTestCase):
    def test_create_rating(self):
        WatchEntry.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=123,
            watched_at=timezone.now(),
        )
        data = {'media_type': 'movie', 'tmdb_id': 123, 'score': 8}
        response = self.client.post('/api/tracking/ratings/', data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Rating.objects.count(), 1)

    def test_upsert_rating(self):
        WatchEntry.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=123,
            watched_at=timezone.now(),
        )
        Rating.objects.create(user=self.user, media_type='movie', tmdb_id=123, score=5)
        data = {'media_type': 'movie', 'tmdb_id': 123, 'score': 9}
        response = self.client.post('/api/tracking/ratings/', data)
        self.assertEqual(response.status_code, 201)
        rating = Rating.objects.first()
        self.assertEqual(rating.score, 9)

    def test_reject_movie_rating_when_not_watched(self):
        response = self.client.post('/api/tracking/ratings/', {'media_type': 'movie', 'tmdb_id': 321, 'score': 7})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Rating.objects.count(), 0)

    def test_reject_movie_rating_when_only_in_watchlist(self):
        UserMediaStatus.objects.create(user=self.user, media_type='movie', tmdb_id=456, status='plan_to_watch', status_changed_at=timezone.now())
        response = self.client.post('/api/tracking/ratings/', {'media_type': 'movie', 'tmdb_id': 456, 'score': 7})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Rating.objects.count(), 0)

    def test_reject_tv_rating_when_none_or_watchlist(self):
        response_none = self.client.post('/api/tracking/ratings/', {'media_type': 'tv', 'tmdb_id': 901, 'score': 7})
        self.assertEqual(response_none.status_code, 400)

        UserMediaStatus.objects.create(user=self.user, media_type='tv', tmdb_id=902, status='plan_to_watch', status_changed_at=timezone.now())
        response_watchlist = self.client.post('/api/tracking/ratings/', {'media_type': 'tv', 'tmdb_id': 902, 'score': 8})
        self.assertEqual(response_watchlist.status_code, 400)

    def test_allow_tv_rating_for_watching_watched_and_dropped(self):
        UserMediaStatus.objects.create(user=self.user, media_type='tv', tmdb_id=910, status='watching')
        UserMediaStatus.objects.create(user=self.user, media_type='tv', tmdb_id=911, status='watched')
        UserMediaStatus.objects.create(user=self.user, media_type='tv', tmdb_id=912, status='dropped')

        response_watching = self.client.post('/api/tracking/ratings/', {'media_type': 'tv', 'tmdb_id': 910, 'score': 8})
        response_watched = self.client.post('/api/tracking/ratings/', {'media_type': 'tv', 'tmdb_id': 911, 'score': 9})
        response_dropped = self.client.post('/api/tracking/ratings/', {'media_type': 'tv', 'tmdb_id': 912, 'score': 6})

        self.assertEqual(response_watching.status_code, 201)
        self.assertEqual(response_watched.status_code, 201)
        self.assertEqual(response_dropped.status_code, 201)

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from media.models import Episode, Season, TVShow
from rest_framework.test import APIClient
from tracking.models import Review, WatchEntry

from .models import Follow

User = get_user_model()


class PrivacyFilteringTests(TestCase):
    def setUp(self):
        self.viewer = User.objects.create_user(username='viewer', password='pass12345')
        self.public = User.objects.create_user(username='public', password='pass12345', account_visibility='public')
        self.private = User.objects.create_user(username='private', password='pass12345', account_visibility='private')
        self.friend = User.objects.create_user(username='friend', password='pass12345', account_visibility='friends_only')
        self.one_way = User.objects.create_user(username='oneway', password='pass12345', account_visibility='friends_only')
        for target in (self.public, self.private, self.friend, self.one_way):
            Follow.objects.create(follower=self.viewer, following=target)
        Follow.objects.create(follower=self.friend, following=self.viewer)
        self.client = APIClient()
        self.client.force_authenticate(user=self.viewer)

    def _authors(self, response):
        return {row['username'] for row in response.data}

    def test_feed_hides_followed_accounts_the_viewer_cannot_see(self):
        for index, user in enumerate((self.public, self.private, self.friend, self.one_way)):
            WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=100 + index, watched_at=timezone.now())

        response = self.client.get('/api/social/feed/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._authors(response), {'public', 'friend'})

    def test_feed_requires_auth(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get('/api/social/feed/').status_code, 401)

    def test_reviews_hide_authors_the_viewer_cannot_see(self):
        for user in (self.viewer, self.public, self.private, self.friend, self.one_way):
            Review.objects.create(user=user, media_type='movie', tmdb_id=550, content=f'{user.username} review')

        response = self.client.get('/api/tracking/reviews/?media_type=movie&tmdb_id=550')

        self.assertEqual(response.status_code, 200)
        contents = {row['content'] for row in response.data['results']}
        self.assertEqual(contents, {'viewer review', 'public review', 'friend review'})

    def test_reviews_require_auth(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get('/api/tracking/reviews/').status_code, 401)

    def test_reviews_reject_invalid_filters(self):
        self.assertEqual(self.client.get('/api/tracking/reviews/?tmdb_id=abc').status_code, 400)
        self.assertEqual(self.client.get('/api/tracking/reviews/?media_type=book').status_code, 400)

    def test_feed_does_not_query_per_entry(self):
        def add_entries(start, count):
            for i in range(start, start + count):
                show = TVShow.objects.create(tmdb_id=700 + i, name=f'Show {i}')
                season = Season.objects.create(show=show, tmdb_id=800 + i, season_number=1, name='Season 1')
                Episode.objects.create(season=season, tmdb_id=900 + i, episode_number=1, name='Pilot')
                WatchEntry.objects.create(
                    user=self.public, media_type='episode', tmdb_id=700 + i,
                    season_number=1, episode_number=1, watched_at=timezone.now(),
                )

        def query_count():
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.client.get('/api/social/feed/').status_code, 200)
            return len(ctx.captured_queries)

        add_entries(0, 2)
        before = query_count()
        add_entries(2, 6)
        self.assertEqual(query_count(), before)

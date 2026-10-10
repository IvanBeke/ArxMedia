from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache as django_cache
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()
class BaseTestCase(TestCase):
    def setUp(self):
        django_cache.clear()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='testuser2',
            email='user2@example.com',
            password='testpass123'
        )
        self.client = APIClient()
        self._tmdb_patchers = [
            patch('media.tmdb.tmdb.sync_movie', return_value=None),
            patch('media.tmdb.tmdb.sync_tv_show', return_value=None),
            patch('tracking.tasks.tmdb.sync_movie', return_value=None),
            patch('tracking.tasks.tmdb.sync_tv_show', return_value=None),
            patch('tracking.tasks.tmdb.sync_season', return_value=None),
        ]
        for patcher in self._tmdb_patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.authenticate()

    def authenticate(self, user=None):
        if user is None:
            user = self.user
        self.client.force_authenticate(user=user)

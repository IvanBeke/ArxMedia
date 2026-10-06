import importlib
import os
from unittest.mock import patch

from accounts.models import User
from django.contrib import admin
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings
from media.models import Episode, EpisodeCredit, Genre, Movie, Season, TVShow
from rest_framework.test import APIClient
from social.models import Follow
from tracking.models import (
    CustomList,
    DataTransferJob,
    ListCollaborator,
    ListItem,
    Rating,
    Review,
    UserMediaStatus,
    WatchEntry,
)


class DatabaseSettingsTests(TestCase):
    def test_atomic_requests_enabled(self):
        self.assertIs(connection.settings_dict['ATOMIC_REQUESTS'], True)


class ProductionSettingsGuardTests(SimpleTestCase):
    STRONG_KEY = 'k' * 50

    def _load(self, module_name, env):
        module = importlib.import_module(f'arxmedia.settings.{module_name}')
        base = importlib.import_module('arxmedia.settings.base')
        self.addCleanup(importlib.reload, module)
        self.addCleanup(importlib.reload, base)
        with patch.dict(os.environ, env, clear=True):
            importlib.reload(base)
            return importlib.reload(module)

    def test_weak_secret_key_rejected_without_debug(self):
        for key in ('short', 'change-me-to-a-long-random-string' + 'x' * 30, 'django-insecure-' + 'x' * 50):
            with self.subTest(key=key), self.assertRaises(ImproperlyConfigured):
                self._load('base', {'DEBUG': 'False', 'SECRET_KEY': key})

    def test_weak_secret_key_allowed_in_debug(self):
        base = self._load('base', {'DEBUG': 'True'})
        self.assertTrue(base.DEBUG)

    def test_database_url_required_without_debug(self):
        with self.assertRaises(ImproperlyConfigured):
            self._load('database', {'DEBUG': 'False', 'SECRET_KEY': self.STRONG_KEY})

    def test_forwarded_host_not_trusted_by_default(self):
        security = self._load('security', {'DEBUG': 'True'})
        self.assertFalse(security.USE_X_FORWARDED_HOST)


UNREACHABLE_REDIS_CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:1/0',
        'OPTIONS': {'IGNORE_EXCEPTIONS': True, 'SOCKET_CONNECT_TIMEOUT': 0.2, 'SOCKET_TIMEOUT': 0.2},
    },
}


@override_settings(CACHES=UNREACHABLE_REDIS_CACHES)
class RedisOutageTests(TestCase):
    def test_login_session_and_throttled_api_work_without_redis(self):
        User.objects.create_user(username='offline', password='Offline-pass-123')
        client = APIClient()

        login = client.post('/api/auth/login/', {'username': 'offline', 'password': 'Offline-pass-123'})
        me = client.get('/api/auth/me/')
        stats = client.get('/api/tracking/stats/')

        self.assertEqual(login.status_code, 200)
        self.assertEqual(me.status_code, 200)
        self.assertEqual(stats.status_code, 200)


class AdminConfigurationTests(TestCase):
    def test_all_models_are_registered(self):
        models = [
            User,
            Genre,
            Movie,
            TVShow,
            Season,
            Episode,
            EpisodeCredit,
            WatchEntry,
            Rating,
            Review,
            CustomList,
            ListItem,
            ListCollaborator,
            UserMediaStatus,
            DataTransferJob,
            Follow,
        ]

        for model in models:
            with self.subTest(model=model.__name__):
                self.assertIn(model, admin.site._registry)

    def test_admins_expose_core_changelist_configuration(self):
        models = [
            Movie,
            TVShow,
            Season,
            Episode,
            EpisodeCredit,
            WatchEntry,
            Rating,
            Review,
            CustomList,
            ListItem,
            ListCollaborator,
            UserMediaStatus,
            DataTransferJob,
            Follow,
        ]

        for model in models:
            model_admin = admin.site._registry[model]
            with self.subTest(model=model.__name__):
                self.assertTrue(model_admin.list_display)
                self.assertTrue(model_admin.search_fields)
                self.assertTrue(model_admin.list_filter)
                self.assertTrue(model_admin.ordering)
                self.assertTrue(model_admin.fieldsets)

        genre_admin = admin.site._registry[Genre]
        self.assertTrue(genre_admin.list_display)
        self.assertTrue(genre_admin.search_fields)
        self.assertTrue(genre_admin.ordering)
        self.assertTrue(genre_admin.fieldsets)

    def test_user_admin_includes_custom_profile_fields(self):
        user_admin = admin.site._registry[User]
        field_names = {
            field_name
            for _, options in user_admin.fieldsets
            for field_name in options['fields']
        }

        self.assertTrue({'bio', 'avatar', 'location', 'website', 'preferred_region', 'account_visibility'} <= field_names)
        self.assertIn('created_at', field_names)

    def test_requested_relationship_ordering(self):
        episode_ordering = ['season__show__name', 'season__season_number', 'episode_number']
        self.assertEqual(
            admin.site._registry[EpisodeCredit].ordering,
            ['episode__season__show__name', 'episode__season__season_number', 'episode__episode_number'],
        )
        self.assertEqual(admin.site._registry[Episode].ordering, episode_ordering)
        self.assertEqual(admin.site._registry[Season].ordering, ['show__name', 'season_number'])
        self.assertEqual(admin.site._registry[ListCollaborator].ordering, ['custom_list'])
        self.assertEqual(
            admin.site._registry[ListItem].ordering,
            ['custom_list__name', 'custom_order', 'added_at'],
        )

    def test_season_admin_displays_related_episode_count(self):
        show = TVShow.objects.create(tmdb_id=910001, name='Admin Count Check')
        season = Season.objects.create(
            show=show,
            tmdb_id=910002,
            season_number=1,
            name='Season 1',
        )
        episode = Episode.objects.create(
            season=season,
            tmdb_id=910003,
            episode_number=1,
            name='Episode 1',
        )

        season_admin = admin.site._registry[Season]
        self.assertEqual(season_admin.episode_count_display(season), 1)
        self.assertEqual(season.episode_count, 1)
        self.assertIsNone(season.air_date)

        episode.air_date = '2024-01-15'
        episode.save(update_fields=['air_date'])
        self.assertEqual(str(season.air_date), '2024-01-15')

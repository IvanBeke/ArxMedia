import importlib
import os
import sys
from unittest.mock import patch

from django.contrib import admin
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import User
from media.models import Episode, EpisodeCredit, Genre, Movie, Season, TVShow
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

    def _load(self, module_name, env, *, argv=None):
        """Reload settings modules under `env`; `argv` simulates a non-test process."""
        names = ['base', 'caching', module_name] if module_name == 'celery' else ['base', module_name]
        modules = [importlib.import_module(f'arxmedia.settings.{name}') for name in names]
        for module in modules:
            self.addCleanup(importlib.reload, module)
        with patch.dict(os.environ, env, clear=True), patch('sys.argv', argv or sys.argv):
            for module in modules:
                importlib.reload(module)
        return modules[-1]

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

    def test_broker_required_without_debug_outside_tests(self):
        env = {'DEBUG': 'False', 'SECRET_KEY': self.STRONG_KEY}
        with self.assertRaisesMessage(ImproperlyConfigured, 'CELERY_BROKER_URL'):
            self._load('celery', env, argv=['gunicorn'])
        celery = self._load('celery', {**env, 'REDIS_URL': 'redis://redis:6379/0'}, argv=['gunicorn'])
        self.assertEqual(celery.CELERY_BROKER_URL, 'redis://redis:6379/1')

    def test_celery_tasks_have_time_limits_and_ignore_results(self):
        celery = self._load('celery', {'DEBUG': 'True'})
        self.assertTrue(celery.CELERY_TASK_IGNORE_RESULT)
        self.assertEqual((celery.CELERY_TASK_SOFT_TIME_LIMIT, celery.CELERY_TASK_TIME_LIMIT), (1800, 2100))
        self.assertEqual(celery.CELERY_BEAT_SCHEDULE['tracking-heartbeat-hourly']['schedule'], 60 * 60)

    def test_celery_time_limits_read_from_env(self):
        celery = self._load('celery', {
            'DEBUG': 'True',
            'CELERY_TASK_SOFT_TIME_LIMIT': '60',
            'CELERY_TASK_TIME_LIMIT': '90',
        })
        self.assertEqual((celery.CELERY_TASK_SOFT_TIME_LIMIT, celery.CELERY_TASK_TIME_LIMIT), (60, 90))

    def test_forwarded_host_not_trusted_by_default(self):
        security = self._load('security', {'DEBUG': 'True'})
        self.assertFalse(security.USE_X_FORWARDED_HOST)


class TestIsolationSettingsTests(SimpleTestCase):
    def test_tests_never_use_shared_redis_or_the_real_broker(self):
        from django.conf import settings

        self.assertTrue(settings.TESTING)
        self.assertEqual(settings.CELERY_BROKER_URL, 'memory://')
        self.assertEqual(settings.CACHES['default']['BACKEND'], 'django.core.cache.backends.locmem.LocMemCache')


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

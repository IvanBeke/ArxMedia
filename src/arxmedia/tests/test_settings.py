import importlib
import os
import sys
from unittest.mock import patch

import pytest
from django.contrib import admin
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.test import override_settings
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

pytestmark = pytest.mark.django_db

class DatabaseSettingsTests:
    def test_atomic_requests_enabled(self):
        assert connection.settings_dict['ATOMIC_REQUESTS'] is True


class ProductionSettingsGuardTests:
    STRONG_KEY = 'k' * 50

    @pytest.fixture(autouse=True)
    def _reload_stack(self, request):
        self._reload_modules = []
        yield
        for module in self._reload_modules:
            importlib.reload(module)

    def _load(self, module_name, env, *, argv=None):
        """Reload settings modules under `env`; `argv` simulates a non-test process."""
        names = ['base', 'caching', module_name] if module_name == 'celery' else ['base', module_name]
        modules = [importlib.import_module(f'arxmedia.settings.{name}') for name in names]
        for module in modules:
            self._reload_modules.append(module)
        with patch.dict(os.environ, env, clear=True), patch('sys.argv', argv or sys.argv):
            for module in modules:
                importlib.reload(module)
        return modules[-1]

    def test_weak_secret_key_rejected_without_debug(self):
        for key in ('short', 'change-me-to-a-long-random-string' + 'x' * 30, 'django-insecure-' + 'x' * 50):
            with pytest.raises(ImproperlyConfigured):
                self._load('base', {'DEBUG': 'False', 'SECRET_KEY': key})

    def test_weak_secret_key_allowed_in_debug(self):
        base = self._load('base', {'DEBUG': 'True'})
        assert base.DEBUG

    def test_database_url_required_without_debug(self):
        with pytest.raises(ImproperlyConfigured):
            self._load('database', {'DEBUG': 'False', 'SECRET_KEY': self.STRONG_KEY})

    def test_broker_required_without_debug_outside_tests(self):
        env = {'DEBUG': 'False', 'SECRET_KEY': self.STRONG_KEY}
        with pytest.raises(ImproperlyConfigured, match='CELERY_BROKER_URL'):
            self._load('celery', env, argv=['gunicorn'])
        celery = self._load('celery', {**env, 'REDIS_URL': 'redis://redis:6379/0'}, argv=['gunicorn'])
        assert celery.CELERY_BROKER_URL == 'redis://redis:6379/1'

    def test_celery_tasks_have_time_limits_and_ignore_results(self):
        celery = self._load('celery', {'DEBUG': 'True'})
        assert celery.CELERY_TASK_IGNORE_RESULT
        assert (celery.CELERY_TASK_SOFT_TIME_LIMIT, celery.CELERY_TASK_TIME_LIMIT) == (1800, 2100)
        assert celery.CELERY_BEAT_SCHEDULE['tracking-heartbeat-hourly']['schedule'] == 60 * 60

    def test_celery_time_limits_read_from_env(self):
        celery = self._load('celery', {
            'DEBUG': 'True',
            'CELERY_TASK_SOFT_TIME_LIMIT': '60',
            'CELERY_TASK_TIME_LIMIT': '90',
        })
        assert (celery.CELERY_TASK_SOFT_TIME_LIMIT, celery.CELERY_TASK_TIME_LIMIT) == (60, 90)

    def test_forwarded_host_not_trusted_by_default(self):
        security = self._load('security', {'DEBUG': 'True'})
        assert not security.USE_X_FORWARDED_HOST


class TestIsolationSettingsTests:
    def test_tests_never_use_shared_redis_or_the_real_broker(self):
        from django.conf import settings

        assert settings.TESTING
        assert settings.CELERY_BROKER_URL == 'memory://'
        assert settings.CACHES['default']['BACKEND'] == 'django.core.cache.backends.locmem.LocMemCache'


UNREACHABLE_REDIS_CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:1/0',
        'OPTIONS': {'IGNORE_EXCEPTIONS': True, 'SOCKET_CONNECT_TIMEOUT': 0.2, 'SOCKET_TIMEOUT': 0.2},
    },
}


class RedisOutageTests:
    @override_settings(CACHES=UNREACHABLE_REDIS_CACHES)
    def test_login_session_and_throttled_api_work_without_redis(self):
        User.objects.create_user(username='offline', password='Offline-pass-123')
        client = APIClient()

        login = client.post('/api/auth/login/', {'username': 'offline', 'password': 'Offline-pass-123'})
        me = client.get('/api/auth/me/')
        stats = client.get('/api/tracking/stats/')

        assert login.status_code == 200
        assert me.status_code == 200
        assert stats.status_code == 200

    @override_settings(CACHES=UNREACHABLE_REDIS_CACHES)
    def test_rate_limits_fail_open_without_redis(self):
        # The login throttle allows 10/minute; exhausting it must not lock
        # anyone out (or 500) when Redis is unreachable.
        User.objects.create_user(username='throttled', password='Offline-pass-123')
        client = APIClient()

        statuses = {
            client.post(
                '/api/auth/login/',
                {'username': 'throttled', 'password': 'wrong-password'},
            ).status_code
            for _ in range(15)
        }

        assert statuses == {401}


class AdminConfigurationTests:
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
            assert model in admin.site._registry

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
            assert model_admin.list_display
            assert model_admin.search_fields
            assert model_admin.list_filter
            assert model_admin.ordering
            assert model_admin.fieldsets

        genre_admin = admin.site._registry[Genre]
        assert genre_admin.list_display
        assert genre_admin.search_fields
        assert genre_admin.ordering
        assert genre_admin.fieldsets

    def test_user_admin_includes_custom_profile_fields(self):
        user_admin = admin.site._registry[User]
        field_names = {
            field_name
            for _, options in user_admin.fieldsets
            for field_name in options['fields']
        }

        assert {'bio', 'avatar', 'location', 'website', 'preferred_region', 'account_visibility'} <= field_names
        assert 'created_at' in field_names

    def test_requested_relationship_ordering(self):
        episode_ordering = ['season__show__name', 'season__season_number', 'episode_number']
        assert admin.site._registry[EpisodeCredit].ordering == ['episode__season__show__name', 'episode__season__season_number', 'episode__episode_number']
        assert admin.site._registry[Episode].ordering == episode_ordering
        assert admin.site._registry[Season].ordering == ['show__name', 'season_number']
        assert admin.site._registry[ListCollaborator].ordering == ['custom_list']
        assert admin.site._registry[ListItem].ordering == ['custom_list__name', 'custom_order', 'added_at']

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
        assert season_admin.episode_count_display(season) == 1
        assert season.episode_count == 1
        assert season.air_date is None

        episode.air_date = '2024-01-15'
        episode.save(update_fields=['air_date'])
        assert str(season.air_date) == '2024-01-15'

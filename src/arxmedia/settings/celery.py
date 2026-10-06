"""Celery and background task settings."""

import os

from celery.schedules import crontab
from django.core.exceptions import ImproperlyConfigured

from .base import DEBUG, TESTING
from .caching import REDIS_URL

if REDIS_URL.endswith('/0'):
    _default_celery_redis_url = REDIS_URL[:-2] + '/1'
elif REDIS_URL:
    _default_celery_redis_url = REDIS_URL + '/1'
else:
    _default_celery_redis_url = ''

CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', _default_celery_redis_url)
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', _default_celery_redis_url)
if TESTING:
    # Tasks queued by tests stay in process memory instead of reaching the dev worker.
    CELERY_BROKER_URL = 'memory://'
    CELERY_RESULT_BACKEND = 'cache+memory://'
elif not CELERY_BROKER_URL and not DEBUG:
    # Without a broker Celery silently falls back to a local AMQP URL and every task is lost.
    raise ImproperlyConfigured('Set REDIS_URL or CELERY_BROKER_URL when DEBUG=False.')
CELERY_TIMEZONE = os.environ.get('TIME_ZONE', 'Europe/Madrid')
CELERY_TASK_ALWAYS_EAGER = os.environ.get('CELERY_TASK_ALWAYS_EAGER', 'False') == 'True'
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
# No caller reads task results; tasks report progress through their database rows.
CELERY_TASK_IGNORE_RESULT = True


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


CELERY_WORKER_CONCURRENCY = _env_int('CELERY_WORKER_CONCURRENCY', 2)
CELERY_WORKER_PREFETCH_MULTIPLIER = _env_int('CELERY_WORKER_PREFETCH_MULTIPLIER', 1)
CELERY_WORKER_MAX_TASKS_PER_CHILD = _env_int('CELERY_WORKER_MAX_TASKS_PER_CHILD', 100)
# Seconds. The soft limit raises SoftTimeLimitExceeded inside the task so it can clean up;
# the hard limit kills the worker process shortly after.
CELERY_TASK_SOFT_TIME_LIMIT = _env_int('CELERY_TASK_SOFT_TIME_LIMIT', 30 * 60)
CELERY_TASK_TIME_LIMIT = _env_int('CELERY_TASK_TIME_LIMIT', 35 * 60)
# The 6-hourly TMDB changes sweep is a serial pass over every changed item, so it gets its own budget.
TMDB_CHANGES_SYNC_SOFT_TIME_LIMIT = _env_int('TMDB_CHANGES_SYNC_SOFT_TIME_LIMIT', 4 * 60 * 60)
TMDB_CHANGES_SYNC_TIME_LIMIT = _env_int('TMDB_CHANGES_SYNC_TIME_LIMIT', 4 * 60 * 60 + 5 * 60)
CELERY_TASK_ANNOTATIONS = {
    'tracking.sync_tmdb_changed_items': {
        'soft_time_limit': TMDB_CHANGES_SYNC_SOFT_TIME_LIMIT,
        'time_limit': TMDB_CHANGES_SYNC_TIME_LIMIT,
    },
}
CELERY_BEAT_SCHEDULE = {
    'tracking-heartbeat-hourly': {
        'task': 'tracking.heartbeat',
        'schedule': 60 * 60,
    },
    'tracking-sync-tmdb-changed-items': {
        'task': 'tracking.sync_tmdb_changed_items',
        'schedule': crontab(hour='*/6', minute=0),
    },
    'tracking-cleanup-data-transfer-jobs-daily': {
        'task': 'tracking.cleanup_data_transfer_jobs',
        'schedule': crontab(hour=5, minute=0),
    },
}

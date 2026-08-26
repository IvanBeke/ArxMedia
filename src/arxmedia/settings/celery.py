"""Celery and background task settings."""

import os

from celery.schedules import crontab

REDIS_URL = os.environ.get('REDIS_URL', '')

if REDIS_URL.endswith('/0'):
    _default_celery_redis_url = REDIS_URL[:-2] + '/1'
elif REDIS_URL:
    _default_celery_redis_url = REDIS_URL + '/1'
else:
    _default_celery_redis_url = ''

CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', _default_celery_redis_url)
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', _default_celery_redis_url)
CELERY_TASK_ALWAYS_EAGER = os.environ.get('CELERY_TASK_ALWAYS_EAGER', 'False') == 'True'
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


CELERY_WORKER_CONCURRENCY = _env_int('CELERY_WORKER_CONCURRENCY', 2)
CELERY_WORKER_PREFETCH_MULTIPLIER = _env_int('CELERY_WORKER_PREFETCH_MULTIPLIER', 1)
CELERY_WORKER_MAX_TASKS_PER_CHILD = _env_int('CELERY_WORKER_MAX_TASKS_PER_CHILD', 100)
CELERY_BEAT_SCHEDULE = {
    'tracking-heartbeat-every-minute': {
        'task': 'tracking.heartbeat',
        'schedule': 60 * 60,
    },
    'tracking-sync-tmdb-changed-items': {
        'task': 'tracking.sync_tmdb_changed_items',
        'schedule': crontab(hour='*/6', minute=0),
    },
}

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
CELERY_BEAT_SCHEDULE = {
    'tracking-heartbeat-every-minute': {
        'task': 'tracking.heartbeat',
        'schedule': 60.0,
    },
    'tracking-sync-tmdb-changed-items-daily': {
        'task': 'tracking.sync_tmdb_changed_items',
        'schedule': crontab(hour=4, minute=0),
    },
}

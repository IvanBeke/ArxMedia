"""Cache settings. Redis is optional: every cache call degrades to a miss when it is unreachable."""

import os

from .base import TESTING

REDIS_URL = os.environ.get('REDIS_URL', '')

if REDIS_URL and not TESTING:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'IGNORE_EXCEPTIONS': True,
                'SOCKET_CONNECT_TIMEOUT': 2,
                'SOCKET_TIMEOUT': 2,
            },
        },
    }
    DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'OPTIONS': {'MAX_ENTRIES': 5000},
        },
    }

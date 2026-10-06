"""Database settings."""

import os

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from .base import BASE_DIR, DEBUG

_db_url = os.environ.get('DATABASE_URL', '')
if not _db_url and not DEBUG:
    raise ImproperlyConfigured('DATABASE_URL must be set when DEBUG=False.')
if _db_url:
    DATABASES = {
        'default': dj_database_url.config(
            default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',
            conn_max_age=600,
        )
    }
    DATABASES['default']['ATOMIC_REQUESTS'] = True
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': str(BASE_DIR / 'db.sqlite3'),
            'CONN_MAX_AGE': 600,
            'ATOMIC_REQUESTS': True,
        }
    }

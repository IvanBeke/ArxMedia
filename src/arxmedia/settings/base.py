"""Core project settings and environment bootstrap."""

import os
import sys
from pathlib import Path

import django_stubs_ext
from django.core.exceptions import ImproperlyConfigured

django_stubs_ext.monkeypatch()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-change-me-in-production')
DEBUG = os.environ.get('DEBUG', 'True') == 'True'
# Test runs must never touch shared Redis state or the real Celery broker.
# Covers `manage.py test` and `pytest` (pytest-django imports settings after
# pytest itself is already in sys.modules). The `gunicorn` carve-out keeps
# ProductionSettingsGuardTests able to simulate a non-test process by patching
# sys.argv: reloading settings under argv=['gunicorn'] must see TESTING=False.
_RUNNER = os.path.basename(sys.argv[0])
TESTING = (
    sys.argv[1:2] == ['test']
    or _RUNNER.startswith(('pytest', 'py.test'))
    or ('pytest' in sys.modules and _RUNNER != 'gunicorn')
)
ALLOWED_HOSTS = [
    host.strip() for host in os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',') if host.strip()
]

if not DEBUG and (len(SECRET_KEY) < 50 or SECRET_KEY.startswith('django-insecure-') or 'change-me' in SECRET_KEY):
    raise ImproperlyConfigured('SECRET_KEY must be a random value of at least 50 characters when DEBUG=False.')

AUTH_USER_MODEL = 'accounts.User'

LANGUAGE_CODE = 'en-us'
TIME_ZONE = os.environ.get('TIME_ZONE', 'Europe/Madrid')
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

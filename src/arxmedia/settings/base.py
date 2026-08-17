"""Core project settings and environment bootstrap."""

import os
from pathlib import Path

import django_stubs_ext
from django.core.exceptions import ImproperlyConfigured

django_stubs_ext.monkeypatch()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-change-me-in-production')
DEBUG = os.environ.get('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',')

if not DEBUG and SECRET_KEY.startswith('django-insecure-'):
    raise ImproperlyConfigured('SECRET_KEY must be set to a strong random value when DEBUG=False.')

AUTH_USER_MODEL = 'accounts.User'

LANGUAGE_CODE = 'en-us'
TIME_ZONE = os.environ.get('TIME_ZONE', 'Europe/Madrid')
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

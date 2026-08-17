"""Security-related Django settings."""

import base64
import hashlib
import os

from django.core.exceptions import ImproperlyConfigured

from .base import DEBUG, SECRET_KEY

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get('SECURE_HSTS_INCLUDE_SUBDOMAINS', 'True') == 'True'
    SECURE_HSTS_PRELOAD = os.environ.get('SECURE_HSTS_PRELOAD', 'True') == 'True'
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_REFERRER_POLICY = 'same-origin'

_fernet_env = os.environ.get('FERNET_KEY', '').strip()
if _fernet_env:
    FERNET_KEY = _fernet_env
else:
    if not DEBUG:
        raise ImproperlyConfigured('FERNET_KEY must be set when DEBUG=False.')
    FERNET_KEY = base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode('utf-8')).digest()).decode('utf-8')

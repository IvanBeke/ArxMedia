"""Static and media file settings."""

from .base import BASE_DIR

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'web' / 'static',
]
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'arxmedia.storage.ViteAwareStaticFilesStorage',
    },
}
# Vite names its assets with a content hash, which WhiteNoise's default test doesn't recognize.
WHITENOISE_IMMUTABLE_FILE_TEST = r'^/static/web/assets/|\.[0-9a-f]{12}\.'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media_uploads'

"""Third-party integration settings."""

import os

from .base import BASE_DIR

TMDB_API_KEY = os.environ.get('TMDB_API_KEY', '')
TMDB_BASE_URL = 'https://api.themoviedb.org/3'
TMDB_IMAGE_BASE_URL = 'https://image.tmdb.org/t/p'

DJANGO_VITE = {
    'default': {
        'dev_mode': os.environ.get('DJANGO_VITE_DEV_MODE', 'False') == 'True',
        'dev_server_protocol': os.environ.get('DJANGO_VITE_DEV_SERVER_PROTOCOL', 'http'),
        'dev_server_host': os.environ.get('DJANGO_VITE_DEV_SERVER_HOST', 'localhost'),
        'dev_server_port': int(os.environ.get('DJANGO_VITE_DEV_SERVER_PORT', '5173')),
        'manifest_path': BASE_DIR / 'web' / 'static' / 'web' / '.vite' / 'manifest.json',
        'static_url_prefix': 'web',
    }
}

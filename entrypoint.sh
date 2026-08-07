#!/bin/sh

set -e

PUID=${PUID:-1000}
PGID=${PGID:-1000}

groupmod -o -g "$PGID" app
usermod -o -u "$PUID" app

chown -R app:app /app /app/media_uploads /app/staticfiles

python manage.py migrate --noinput

exec gunicorn arxmedia.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120

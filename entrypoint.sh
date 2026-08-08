#!/bin/sh

set -e

PUID=${PUID:-1000}
PGID=${PGID:-1000}

if [ "$(id -u)" -eq 0 ]; then
    if [ "$(id -g app)" != "$PGID" ]; then
        groupmod -o -g "$PGID" app
    fi
    if [ "$(id -u app)" != "$PUID" ]; then
        usermod -o -u "$PUID" app
    fi
    chown -R app:app /app/media_uploads /app/staticfiles
fi

python manage.py migrate --noinput

exec gunicorn arxmedia.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 120 \
    --log-level "${GUNICORN_LOG_LEVEL:-info}" \
    --access-logfile - \
    --error-logfile - \
    --capture-output

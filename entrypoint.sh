#!/bin/sh

set -e

PUID=${PUID:-1000}
PGID=${PGID:-1000}

# Adjust ids and volume ownership as root, then re-exec as the unprivileged app user.
if [ "$(id -u)" -eq 0 ]; then
    if [ "$(id -g app)" != "$PGID" ]; then
        groupmod -o -g "$PGID" app
    fi
    if [ "$(id -u app)" != "$PUID" ]; then
        usermod -o -u "$PUID" app
    fi
    chown -R app:app /app/media_uploads /app/staticfiles
    exec setpriv --reuid=app --regid=app --init-groups "$0" "$@"
fi

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

python manage.py migrate --noinput

exec gunicorn arxmedia.wsgi:application \
    --bind 0.0.0.0:8000 \
    --worker-class gthread \
    --workers "${GUNICORN_WORKERS:-3}" \
    --threads "${GUNICORN_THREADS:-4}" \
    --timeout 240 \
    --log-level "${GUNICORN_LOG_LEVEL:-info}" \
    --access-logfile - \
    --error-logfile - \
    --capture-output

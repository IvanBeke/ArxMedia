# ArxMedia

ArxMedia is a self-hosted media tracking app built with Django REST Framework and Vue 3.

## What it does

- Search movies and TV shows via TMDB
- Track watch history, ratings, and reviews
- Manage a watchlist
- Follow users and see social activity
- View personal dashboard stats

## Stack

- Backend: Django 6, Django REST Framework, SimpleJWT
- Frontend: Vue 3, Pinia, Vue Router, Tailwind CSS
- Runtime: Python 3.14, Node 22
- Data: SQLite (local default), PostgreSQL 17 (containerized)
- Services: Redis, Celery worker, Celery beat

## Quick start (Docker)

1. Get a free TMDB API key at `https://www.themoviedb.org/settings/api`.
2. Copy `.env.example` to `.env` and set `TMDB_API_KEY`.
3. Configure Django-Vite mode by environment:
   - Development: `DJANGO_VITE_DEV_MODE=True` (with `DJANGO_VITE_DEV_SERVER_PROTOCOL/HOST/PORT` matching your Vite dev server).
   - Production: `DJANGO_VITE_DEV_MODE=False` (Django serves built assets from `src/web/static/web`).
4. Start the stack and run migrations.

```bash
cp .env.example .env
# edit .env (at minimum: SECRET_KEY, TMDB_API_KEY, FERNET_KEY, DB password values)

docker compose up --build -d
docker compose exec app python manage.py migrate
docker compose exec app python manage.py createsuperuser  # optional
```

App URL: `http://localhost:8000`

## Key paths

- Django settings: `src/arxmedia/settings.py`
- Django URLs: `src/arxmedia/urls.py`
- Backend apps: `src/accounts`, `src/media`, `src/tracking`, `src/social`, `src/my_calendar`, `src/web`
- UI source: `src/web/ui/src`
- Built UI assets: `src/web/static/web`

## API base routes

- `/api/auth/`
- `/api/media/`
- `/api/tracking/`
- `/api/social/`
- `/api/calendar/`

All non-API routes fall back to the SPA.

## Useful commands

```bash
# verify harness and environment
./init.sh

# check services
docker compose ps

# show migration state
docker compose exec app python manage.py showmigrations

# run a Django command
docker compose exec app python manage.py <command>

# run focused tests
docker compose exec app python manage.py test <module_or_class> --keepdb

# regenerate backend lockfile (uv.lock)
docker run --rm -v "$(pwd)/src:/workspace" -w /workspace ghcr.io/astral-sh/uv:python3.14-bookworm uv lock

# regenerate frontend lockfile (pnpm-lock.yaml)
docker run --rm -e CI=true -v "$(pwd)/src/web:/workspace" -w /workspace/ui node:22-alpine sh -lc "corepack enable && corepack prepare pnpm@latest --activate && pnpm install --no-frozen-lockfile"

# build UI production assets
docker run --rm -e CI=true -v "$(pwd)/src/web:/workspace" -w /workspace/ui node:22-alpine sh -lc "corepack enable && corepack prepare pnpm@latest --activate && pnpm install && pnpm build"
```

## Production

Use `compose.prod.yaml` directly. It is a complete production stack and pulls the published image.
Production serves static assets from the image with WhiteNoise (no `static_files` volume mount in prod).

```bash
docker compose -f compose.prod.yaml up -d
```

## Notes

- This project is primarily tailored for personal self-hosted usage.
- Keep secrets in `.env` only; do not commit real credentials.
- Redis defaults are split: `REDIS_URL` uses DB `0` (cache) and Celery uses DB `1` (`CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`).
- Contribution and security expectations are in `CONTRIBUTING.md` and `SECURITY.md`.

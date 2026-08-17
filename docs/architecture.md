# docs/architecture.md - ArxMedia

What "good work" means for this project.

## Project philosophy

- **Always Docker Compose** — no system venvs, no bare Python
- **Minimum change** — implement only what the feature requires, no scope creep
- **Progressive disclosure** — AGENTS.md is the map, not the encyclopedia. Agents reference docs for details.
- **Verification-first reporting** — repository state and command output are the source of truth

## App principles (Django)

- Models are sync from TMDB — the app does not own media catalog
- JWT auth with 1h access, 7d refresh, rotate tokens
- Redis cache is optional — TMDB service falls back gracefully
- DRF with `IsAuthenticatedOrReadOnly` and `PageNumberPagination` (PAGE_SIZE=20)
- All Django code lives under `src/`

## Settings layout

- Django settings are split into `src/arxmedia/settings/` with `DJANGO_SETTINGS_MODULE=arxmedia.settings`
- `src/arxmedia/settings/__init__.py` loads and exports uppercase settings from all modules in deterministic order
- `src/arxmedia/settings/base.py` defines bootstrap/core values (`BASE_DIR`, `SECRET_KEY`, `DEBUG`, locale/timezone, auth user model)
- `src/arxmedia/settings/security.py` contains security flags, cookie/CSRF hardening, and `FERNET_KEY` resolution
- `src/arxmedia/settings/django_core.py` contains installed apps, middleware, templates, root urls, and WSGI entry
- `src/arxmedia/settings/database.py` contains `DATABASES` and `dj-database-url` fallback logic
- `src/arxmedia/settings/static_media.py` contains static/media paths and storages
- `src/arxmedia/settings/api.py` contains password validators, DRF, JWT, and CORS/CSRF trusted origins
- `src/arxmedia/settings/integrations.py` contains TMDB and Django Vite integration settings
- `src/arxmedia/settings/celery.py` contains Redis-derived Celery broker/backend and beat schedules
- `src/arxmedia/settings/logging_conf.py` contains `LOG_LEVEL` and Django logging configuration

## UI principles (Vue 3)

- Dark theme, purple brand (#9f42c6), Inter font
- UI source lives under `src/web/ui/src/`
- Built ui assets are served by Django from `src/web/static/web/`
- OAuth endpoints live under `/oauth/*` and are handled fully in app
- Routes: `/movies`, `/movies/:id`, `/tv`, `/tv/:id`, `/tv/:id/season/:seasonNumber`, `/search`, `/dashboard`, `/watchlist`, `/history`, `/profile/:username`, `/settings`

## Profile visibility and social graph contract

- Account visibility values are `public`, `private`, and `friends_only`
- Friendship is defined as a mutual follow (`A follows B` and `B follows A`)
- Visibility rules for protected profile data:
  - `public`: everyone can view protected sections
  - `private`: only the profile owner can view protected sections
  - `friends_only`: owner + mutual followers can view protected sections
- `GET /api/auth/users/<username>/` always returns base profile identity fields and includes:
  - `viewer_relationship`: `is_self`, `is_following`, `follows_you`, `is_friend`
  - `permissions`: `can_view_activity`, `can_view_lists`
  - `stats`: `ratings_count`, `watchlist_count`, `average_rating` (null when hidden)
  - `visible_lists`: filtered by account visibility and list privacy
  - `recent_activity`: recent watched entries when visible
- Social graph endpoints:
  - `GET /api/auth/users/<username>/followers/`
  - `GET /api/auth/users/<username>/following/`
  - both use DRF page-number pagination (`count`, `next`, `previous`, `results`)
  - both return `403` when viewer cannot access protected account content

## Database

- SQLite for dev (default), PostgreSQL 17 for prod via `dj-database-url`
- Models under `src/*/models.py`
- Migrations via `docker compose exec app python manage.py migrate`

## External integrations

- TMDB API required for all media search/trending/popular
- Redis 7 for TMDB response caching (7-day TTL, nx=True) — optional

## What "good" looks like

- Feature implemented per specification
- `init.sh` passes
- No new lint errors or warnings
- Tests exist and pass
- No regressions to existing functionality
- Changes are minimal and focused

## Feature architecture docs

- Import pipeline architecture (tracking): `docs/import-pipeline.md`

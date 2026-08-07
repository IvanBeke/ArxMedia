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

## UI principles (Vue 3)

- Dark theme, purple brand (#9f42c6), Inter font
- UI source lives under `src/web/ui/src/`
- Built ui assets are served by Django from `src/web/static/web/`
- OAuth endpoints live under `/oauth/*` and are handled fully in app
- Routes: `/movies`, `/movies/:id`, `/tv`, `/tv/:id`, `/tv/:id/season/:seasonNumber`, `/search`, `/dashboard`, `/watchlist`, `/history`, `/profile/:username`, `/settings`

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

# AGENTS.md - ArxMedia

Only keep changes minimal and scoped. If the user instruction conflicts with repo habits, follow the user.

## Canonical harness guide

- This file is the single source of truth for harness workflow and execution rules.
- Process tasks directly from user requests; do not rely on backlog tracker files.

## Non-negotiables

- Use Docker for all app/UI operations; do not run host Python/Node tooling.
- Run commands from repo root.
- Validate with `./init.sh` before declaring done.
- Commit messages must follow the existing repository pattern: `<type>(<scope>): <imperative summary>`.

## Real project shape (verified)

- Django app lives in `src/`; settings and URLs are `src/arxmedia/settings.py` and `src/arxmedia/urls.py`.
- UI source is embedded at `src/web/ui/src`; built assets output to `src/web/static/web` via Vite.
- API mounts: `/api/auth`, `/api/media`, `/api/tracking`, `/api/social`, `/api/calendar`; all non-API routes fall back to SPA.
- Docker services in `compose.yaml`: `app`, `db`, `redis`, `worker`, `beat`, `ui`.

## Commands agents usually guess wrong

- Start stack: `docker compose up --build -d`
- Migrations: `docker compose exec app python manage.py migrate`
- App command: `docker compose exec app python manage.py <command>`
- App lint: `docker compose exec app uv run ruff check accounts media tracking social my_calendar web arxmedia --fix`
- App types: `docker compose exec app uv run mypy accounts media tracking social my_calendar web arxmedia`
- Targeted tests (non-interactive-safe): `docker compose exec app python manage.py test <module_or_class> --keepdb`
- UI production build (required path):
  `docker run --rm -e CI=true -v "$(pwd)/src/web:/workspace" -w /workspace/ui node:22-alpine sh -lc "corepack enable && corepack prepare pnpm@latest --activate && pnpm install && pnpm build"`

## Verification order

1. `./init.sh`
2. `docker compose ps` (services must be Up)
3. `docker compose exec app python manage.py showmigrations` (no `[ ]`)
4. Relevant focused tests
5. Both lint and type checks
6. UI build command above if UI touched

## High-signal implementation quirks

- Python runtime is 3.14 (`src/pyproject.toml` + Dockerfile); dependency install uses `uv` in Docker.
- TMDB is the source of truth for movie/TV metadata; local models are synced/cache-backed (Redis optional).
- Vite dev proxy targets `http://app:8000` (service name), not localhost.
- UI uses Vue 3 Composition API (`<script setup>`) and `@` alias.

## Simple workflow

- Start from the user task and apply the smallest focused change that solves it.
- Finish features end-to-end in one pass whenever possible: include connected backend/frontend/tests/verification work that is required for the feature to be truly complete, not just partially implemented.
- Treat feature completion as cross-layer by default: cover all directly affected logic/API/UI paths and keep parallel surfaces (e.g., movie/TV equivalents) in parity unless the user explicitly scopes otherwise.
- Include behavioral edge states in the first delivery when applicable: loading, empty, error, and permission-denied flows.
- If you add or change a mutation path (endpoint/action), update related read paths and UI state in the same change so users see consistent results immediately.
- API changes must ship contract-complete in one set: auth expectations, validation behavior, response shape, and frontend consumption.
- Add or update regression tests for touched feature behavior, not only happy-path checks.
- Do not defer core requested behavior silently: if anything essential is intentionally deferred, explicitly mark it out of scope with a reason before declaring done.
- Before reporting completion, run a feature-complete check: request fully implemented, edge states handled, focused tests updated, lint/types passing, and user-visible behavior verified.
- Keep implementation and verification evidence in command output and final report.
- Define task-specific ad-hoc checks from the request and touched code paths.

## Existing instruction sources worth checking

- `docs/architecture.md`, `docs/conventions.md`, `docs/verification.md`
- `CHECKPOINTS.md`

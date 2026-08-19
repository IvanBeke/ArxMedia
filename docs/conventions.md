# docs/conventions.md - ArxMedia

Code style, patterns, and no-gos for this project.

## App (Python/Django)

### Style
- 4-space indentation, no tabs
- Snake_case for variables and functions
- PascalCase for classes and models
- Max line length: 120 (black compatible)

### Patterns
- Use `django.conf.settings` for config, never hardcode
- Use `from django.db.models import Q` for complex queries
- Use `select_related` and `prefetch_related` for performance
- Use `SerializerMethodField` for computed fields in DRF serializers
- Wrap external API calls in try/except with fallback
- Use Docker Compose: `docker compose exec app ...`
- Use `uv` for app tooling inside Docker (`docker compose exec app uv ...`)
- Add new Django settings in `src/arxmedia/settings/` by domain (`base`, `security`, `django_core`, `database`, `static_media`, `api`, `integrations`, `celery`, `logging_conf`), not in a monolithic file
- Keep `src/arxmedia/settings/__init__.py` as the only aggregation entrypoint that exports uppercase settings loaded from those modules

### No-gos
- No bare `except:` — always catch specific exceptions
- No `print()` in production code — use logging
- No hardcoded secrets — use environment variables
- No schema-breaking migration shortcuts (dropping data/columns without an explicit migration path)

## UI (Vue 3)

### Style
- Composition API (`<script setup>`)
- Snake_case for Vue component props
- PascalCase for components
- Use `@/` alias for imports

### Patterns
- Use Pinia stores for state management
- Use `async/await` for API calls
- Use `v-if/v-else` for conditional rendering
- Use `<script setup>` with `defineProps`/`defineEmits`
- Run UI tooling in Docker using a Node container mounted to `src/web/ui`

### No-gos
- No Option API (`data()`, `methods`, etc.)
- No jQuery
- No inline styles — use Tailwind classes
- No Vue Router navigation without auth guard

## Testing

- App: pytest with pytest-django (if tests exist)
- UI: Vitest (if tests exist)
- Minimum coverage: models, views, serializers, critical paths

## Git conventions

- Commits in English, imperative mood ("add search filters", not "added")
- One feature per branch (if using branches)
- PR description includes scope, verification commands, and migration impact (if any)

## Docker

- Always use `docker compose` (not `docker-compose`)
- App service name: `app`
- UI service name: `ui`
- Redis service name: `redis` (if used)
- Never run app/UI tooling on host; run through Docker services only
- App commands: `docker compose exec app ...` (`uv`/`python`)
- UI build command: `docker compose exec ui sh -lc "pnpm install && pnpm build"`

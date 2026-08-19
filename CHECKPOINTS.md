# CHECKPOINTS.md - ArxMedia

Criteria for a feature to be considered `done`.

## Universal checkpoints (all features must pass)

1. **`init.sh` exits 0** — no regressions, all checks pass
2. **Docker Compose services healthy** — `docker compose ps` shows all services running
3. **App migrations applied** — `docker compose exec app python manage.py showmigrations` shows no unapplied migrations
4. **No breaking changes to existing APIs** — existing endpoints still respond correctly
5. **No hardcoded secrets** — no API keys, tokens, or secrets in source code
6. **Embedded UI builds without errors** — `docker compose exec ui sh -lc "pnpm install && pnpm build"` exits 0

## Task-specific checkpoints

Define checkpoints per request based on the acceptance criteria and changed code paths.

Examples:

- API changes: verify endpoint responses and auth behavior
- Data model changes: verify migrations are applied and related queries still work
- UI changes: verify route/component behavior and run the UI production build

## Verification commands

```bash
# Full verification
./init.sh

# Manual checks
docker compose ps
docker compose exec app python manage.py showmigrations
curl -s http://localhost:8000/api/media/trending/?type=movie | jq -e '.results'
```

## Anti-regression rules

- Never drop database tables
- Never remove existing API endpoints without migration path
- Never break JWT auth flow
- Never remove Redis cache gracefully (it should still work without it)

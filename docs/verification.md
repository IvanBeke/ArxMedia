# docs/verification.md - ArxMedia

How to prove a feature works.

## Pre-flight checks

Before calling a feature `done`, verify:

### 1. Init script passes
```bash
./init.sh
```
Must exit 0 with all checks green.

### 2. Services healthy
```bash
docker compose ps
```
All services must show `Up` status.

### 3. No unapplied migrations
```bash
docker compose exec app python manage.py showmigrations
```
Every app should show all migrations as `[X]` (applied), none as `[ ]`.

### 4. API responds correctly

Auth is session-cookie based. Save cookies to a jar, log in (CSRF token required), then call authenticated endpoints:

```bash
JAR=$(mktemp)
curl -s -c "$JAR" http://localhost:8000/ -o /dev/null
TOKEN=$(grep csrftoken "$JAR" | awk '{print $NF}')

# Register (201 + session cookie) or log in (200)
curl -s -c "$JAR" -b "$JAR" -H "X-CSRFToken: $TOKEN" -H 'Content-Type: application/json' \
  -d '{"username":"smoke","email":"s@example.com","password":"Smoke-pass-123","password2":"Smoke-pass-123"}' \
  http://localhost:8000/api/auth/register/ | jq -e '.username'

# Authenticated endpoints (401 without the session cookie)
curl -s -b "$JAR" http://localhost:8000/api/auth/me/ | jq -e '.username'
curl -s -b "$JAR" "http://localhost:8000/api/media/search/?q=inception&type=movie" | jq -e '.results'
curl -s -b "$JAR" "http://localhost:8000/api/media/trending/?type=movie" | jq -e '.results'
```

### 5. Backend checks

```bash
docker compose exec app python manage.py test
docker compose exec app uv run ruff check . --fix
docker compose exec app uv run mypy .
```

### 6. UI checks (run the build only if UI files were touched)

```bash
docker compose exec ui sh -lc "pnpm typecheck"
docker compose exec ui sh -lc "pnpm test"
docker compose exec ui sh -lc "pnpm install && pnpm build"
```

### 7. Task-specific ad-hoc checks

Define checks from the current user request and the code paths you touched.

Examples:

```bash
# API behavior check (authenticated; see step 4 for the session setup)
curl -s -b "$JAR" "http://localhost:8000/api/media/search/?q=inception&type=movie" | jq -e '.results'

# Auth/me endpoint check (when auth code changes)
curl -s -b "$JAR" http://localhost:8000/api/auth/me/ | jq -e '.username'
```

Use focused checks that prove the requested behavior and guard against regressions in nearby functionality.

## What "passing" means

- All commands exit 0
- No errors in docker compose logs
- API responses match expected schema
- UI renders without console errors

## What "failing" looks like

- `init.sh` exits non-zero
- Service shows `Exit` or `Restarting` in `docker compose ps`
- Unapplied migrations in `showmigrations`
- API returns 500 or unexpected error
- UI type check or build fails

## Recovery

If verification fails:
1. Read error output
2. Identify root cause
3. Fix with minimum change
4. Re-run verification
5. Never ignore failures — they must be resolved before marking `done`

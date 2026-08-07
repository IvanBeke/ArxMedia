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
```bash
# Trending movies
curl -s http://localhost:8000/api/media/trending/?type=movie | jq -e '.results'

# Search
curl -s "http://localhost:8000/api/media/search/?q=inception&type=movie" | jq -e '.results'

# Auth endpoint
curl -s http://localhost:8000/api/auth/register/ | jq -e '.username'
```

### 5. Embedded UI builds
```bash
docker run --rm -e CI=true -v "$(pwd)/src/web:/workspace" -w /workspace/ui node:22-alpine sh -lc "corepack enable && corepack prepare pnpm@latest --activate && pnpm install && pnpm build"
```
Must exit 0.

### 6. Task-specific ad-hoc checks

Define checks from the current user request and the code paths you touched.

Examples:

```bash
# API behavior check
curl -s "http://localhost:8000/api/media/search/?q=inception&type=movie" | jq -e '.results'

# Auth/me endpoint check (when auth code changes)
curl -s -H "Authorization: Bearer <token>" http://localhost:8000/api/auth/me/ | jq -e '.username'
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
- UI build fails

## Recovery

If verification fails:
1. Read error output
2. Identify root cause
3. Fix with minimum change
4. Re-run verification
5. Never ignore failures — they must be resolved before marking `done`

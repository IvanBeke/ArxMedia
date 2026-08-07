## Summary

- What changed?
- Why?

## Scope

- [ ] Backend
- [ ] Frontend
- [ ] Infrastructure/DevEx
- [ ] Docs only

## Verification

Commands run (from repo root):

```bash
./init.sh
docker compose ps
docker compose exec app python manage.py showmigrations
```

Task-specific ad-hoc checks:

```bash
# add the exact commands you ran
```

If UI code was touched:

```bash
docker run --rm -e CI=true -v "$(pwd)/src/web:/workspace" -w /workspace/ui node:22-alpine sh -lc "corepack enable && corepack prepare pnpm@latest --activate && pnpm install && pnpm build"
```

## Migration impact

- [ ] No migration changes
- [ ] Migration added
- [ ] Migration requires manual ops

Notes:

## Checklist

- [ ] Changes are minimal and scoped
- [ ] No secrets added
- [ ] Docs updated if behavior changed

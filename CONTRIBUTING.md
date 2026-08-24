# Contributing to ArxMedia

Thanks for contributing.

## Maintainer scope disclaimer

I built this app around my own day-to-day usage and preferences.

Contributions are welcome, but I may decline changes that do not match how I want this project to evolve or how I personally use it.

## Workflow

- Start from a clear task or issue.
- Keep changes minimal and scoped.
- Use Docker for all app and UI operations.
- Run commands from the repository root.

## Local setup

```bash
cp .env.example .env
docker compose up -d
docker compose exec app python manage.py migrate
```

`up -d` auto-builds missing images. Add `--build` only after changing the `Dockerfile`
or backend dependencies — see the "Dependencies" section in `README.md`.

## Verification required before opening a PR

Run, in this order:

```bash
./init.sh
docker compose ps
docker compose exec app python manage.py showmigrations
```

Then run focused ad-hoc checks for the behavior you changed. Examples:

```bash
docker compose exec app python manage.py test <module_or_class> --keepdb
curl -s "http://localhost:8000/api/media/search/?q=inception&type=movie" | jq -e '.results'
```

If UI code is touched, also run:

```bash
docker compose exec ui sh -lc "pnpm install && pnpm build"
```

## Style and conventions

- Python: follow `docs/conventions.md`.
- Vue: Composition API with `@/` imports.
- Do not hardcode secrets.

## Pull requests

- Use an imperative title/message style.
- Describe scope, verification commands run, and any migration impact.
- Include screenshots for UI changes when helpful.

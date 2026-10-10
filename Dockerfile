FROM ghcr.io/pnpm/pnpm:12 AS uibuild

WORKDIR /ui

COPY src/web/ui/package.json src/web/ui/pnpm-lock.yaml src/web/ui/pnpm-workspace.yaml ./
RUN CI=true pnpm install --frozen-lockfile

COPY src/web/ui/ ./
RUN pnpm build


FROM python:3.14-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=ghcr.io/astral-sh/uv:0.12.24 /uv /usr/local/bin/uv

WORKDIR /app

COPY src/pyproject.toml src/uv.lock ./
RUN uv export --format requirements.txt --no-dev --frozen -o /tmp/requirements.txt && \
    uv pip install --system --prefix /install --requirement /tmp/requirements.txt && \
    rm -f /tmp/requirements.txt


FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local
COPY --from=ghcr.io/astral-sh/uv:0.12.24 /uv /usr/local/bin/uv

COPY src/ .

# Built assets come from the uibuild stage (vite outDir is ../static/web).
COPY --from=uibuild /static/web ./web/static/web

RUN python manage.py collectstatic --noinput

RUN mkdir -p /app/media_uploads /app/staticfiles && \
    groupadd -g 1000 app && useradd -u 1000 -g app -M -d /nonexistent -s /usr/sbin/nologin app && \
    chown -R app:app /app /app/media_uploads /app/staticfiles

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]

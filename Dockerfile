FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ca-certificates \
    gnupg \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get update && apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv

COPY src/pyproject.toml src/uv.lock ./
RUN uv export --format requirements.txt --no-dev --frozen -o /tmp/requirements.txt && \
    uv pip install --system --requirement /tmp/requirements.txt && \
    rm -f /tmp/requirements.txt

COPY src/ .

RUN npm install -g pnpm@11 && \
    cd /app/web/ui && \
    CI=true pnpm install && \
    CI=true pnpm build

RUN python manage.py collectstatic --noinput

RUN mkdir -p /app/media_uploads /app/staticfiles && \
    groupadd -r app && useradd -r -g app -d /app -s /usr/sbin/nologin app && \
    chown -R app:app /app /app/media_uploads /app/staticfiles

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

CMD ["/entrypoint.sh"]

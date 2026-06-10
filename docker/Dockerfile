FROM python:3.11-slim-bullseye AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

FROM base AS builder

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev --no-install-project

COPY backend /app/backend
COPY scripts /app/scripts

RUN AI_STORY_COMPILE_CLOSED_SOURCE=1 /opt/venv/bin/python /app/backend/manage.py setup_in_docker \
    && /app/scripts/check_closed_source_apps.sh

FROM python:3.11-slim-bullseye AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/backend /app/backend
COPY docker/backend-entrypoint.sh /usr/local/bin/backend-entrypoint

RUN sed -i 's/\r$//' /usr/local/bin/backend-entrypoint \
    && chmod +x /usr/local/bin/backend-entrypoint \
    && mkdir -p staticfiles media logs

EXPOSE 8010

ENTRYPOINT ["/usr/local/bin/backend-entrypoint"]
CMD ["gunicorn", "--chdir", "/app/backend", "config.wsgi:application", "--bind", "0.0.0.0:8010"]

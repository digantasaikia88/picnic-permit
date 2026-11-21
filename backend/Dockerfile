# syntax=docker/dockerfile:1

# ---------- base: Python and uv ----------
FROM python:3.14.10-slim-trixie AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/opt/venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:0.13.9 /uv /uvx /usr/local/bin/

# WeasyPrint (permit PDF) draws text with Pango. DejaVu is the font of the PDFs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app /opt/venv /data/uploads \
    && chown -R app:app /app /opt/venv /data

WORKDIR /app

# ---------- dev: all dependencies, source is bind-mounted, auto-reload ----------
FROM base AS dev

USER app
COPY --chown=app:app pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "app"]

# ---------- builder: runtime dependencies only ----------
FROM base AS builder

ENV UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ---------- prod: small image, no uv, no dev tools, non-root ----------
FROM python:3.14.10-slim-trixie AS prod

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# WeasyPrint (permit PDF) draws text with Pango. DejaVu is the font of the PDFs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app /data/uploads \
    && chown -R app:app /app /data

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app app ./app
COPY --chown=app:app --chmod=755 entrypoint.prod.sh ./

USER app
EXPOSE 8000
CMD ["./entrypoint.prod.sh"]

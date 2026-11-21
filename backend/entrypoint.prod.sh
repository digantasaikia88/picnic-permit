#!/bin/sh
# Production start: apply database migrations, then run the API without reload.
set -eu

echo "Applying database migrations..."
alembic upgrade head

echo "Starting API with ${UVICORN_WORKERS:-2} worker(s)..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${UVICORN_WORKERS:-2}" \
    --proxy-headers \
    --forwarded-allow-ips "*"

#!/bin/sh
# Run migrations and seed data as a one-shot step before starting the server.
# Separating this from the server process lets Kubernetes/Compose run it as an
# init container so the API never starts with a stale schema.
set -e

echo "[entrypoint] Running Alembic migrations..."
alembic -c /app/alembic.ini upgrade head

echo "[entrypoint] Seeding country configs..."
python /app/backend/fastapi/scripts/seed_countries.py

echo "[entrypoint] Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 6969

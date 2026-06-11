#!/bin/sh
# Run migrations and seed data as a one-shot step before starting the server.
# Separating this from the server process lets Kubernetes/Compose run it as an
# init container so the API never starts with a stale schema.
set -e

echo "[entrypoint] Running Alembic migrations..."
# ALEMBIC_DATABASE_URL bypasses PgBouncer for migrations (DDL not compatible with
# transaction pool mode). alembic/env.py reads this env var automatically.
alembic -c /app/alembic.ini upgrade head

echo "[entrypoint] Seeding country configs..."
python /app/backend/fastapi/scripts/seed_countries.py

echo "[entrypoint] Seeding platform wallet user..."
# Creates the ZASKA platform user + wallets for all currencies if they don't exist.
# The script prints ONLY the user_id to stdout — we capture it here.
#
# Auto-set ZASKA_WALLET_USER_ID if not already configured in the environment.
# Priority:
#   1. ZASKA_WALLET_USER_ID already set in env (explicit production config) → kept as-is
#   2. Not set → derived from the seeded platform user → exported for this process
#
# This means operators do NOT need to manually configure ZASKA_WALLET_USER_ID —
# it is resolved automatically at every startup.  The env var override still works
# for environments where the platform wallet is managed separately.
_SEEDED_PLATFORM_ID=$(python /app/backend/fastapi/scripts/seed_platform_wallet.py)

if [ -z "${ZASKA_WALLET_USER_ID:-}" ] && [ -n "$_SEEDED_PLATFORM_ID" ]; then
    export ZASKA_WALLET_USER_ID="$_SEEDED_PLATFORM_ID"
    echo "[entrypoint] ZASKA_WALLET_USER_ID auto-set from seed: ${ZASKA_WALLET_USER_ID}"
elif [ -n "${ZASKA_WALLET_USER_ID:-}" ]; then
    echo "[entrypoint] ZASKA_WALLET_USER_ID already configured: ${ZASKA_WALLET_USER_ID}"
fi

echo "[entrypoint] Seeding social fund wallet users..."
_SEEDED_SOCIAL_EXPORTS=$(python /app/backend/fastapi/scripts/seed_social_funds.py)

for _ASSIGNMENT in $_SEEDED_SOCIAL_EXPORTS; do
    case "${_ASSIGNMENT}" in
        *=*) ;;
        *) continue ;;  # not a KEY=VALUE token (e.g. stray log noise) — skip
    esac

    _KEY=${_ASSIGNMENT%%=*}
    _VALUE=${_ASSIGNMENT#*=}

    # Only allow shell-identifier-safe keys (POSIX: [A-Za-z_][A-Za-z0-9_]*)
    # before handing _KEY to eval. Anything else is skipped to avoid
    # "Bad substitution" / arbitrary-expansion from unexpected tokens.
    case "${_KEY}" in
        [A-Za-z_]*)
            case "${_KEY}" in
                *[!A-Za-z0-9_]*) continue ;;
            esac
            ;;
        *) continue ;;
    esac

    [ -z "${_VALUE}" ] && continue

    eval "_CURRENT=\${${_KEY}:-}"
    if [ -z "${_CURRENT}" ]; then
        export "${_KEY}=${_VALUE}"
        echo "[entrypoint] ${_KEY} auto-set from seed: ${_VALUE}"
    else
        echo "[entrypoint] ${_KEY} already configured: ${_CURRENT}"
    fi
done

echo "[entrypoint] Starting API server..."

# WEB_CONCURRENCY: number of uvicorn worker processes.
# Default 1: safe for in-process scheduler (Redis locks protect against concurrent
# job execution across replicas, but extra threads waste memory at small scale).
# Set WEB_CONCURRENCY=$(nproc) for multi-core production servers.
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 6969 \
    --workers "${WEB_CONCURRENCY:-1}" \
    --timeout-keep-alive 30 \
    --limit-max-requests 1000 \
    --loop uvloop \
    --http h11

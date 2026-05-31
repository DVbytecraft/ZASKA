#!/usr/bin/env bash
# deploy_migration_0039.sh — Safe deployment of Alembic migration 0039
#
# Migration 0039 adds: trust_scores, badges, user_badges, skills, user_skills,
#   photo_verifications, moderation_cases tables + 5 new User columns.
#
# Prerequisites:
#   - DATABASE_URL env var set (or .env loaded)
#   - pg_dump, psql, alembic available on PATH
#   - Running as a user with CREATEDB + ALTER TABLE privileges
#
# Usage:
#   chmod +x scripts/deploy_migration_0039.sh
#   ./scripts/deploy_migration_0039.sh
#
# Rollback:
#   alembic downgrade 0038  (runs migration 0039's downgrade() function)
#   OR restore from backup: psql "$DATABASE_URL" < /tmp/zaska_pre_0039_<timestamp>.sql

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="/tmp/zaska_pre_0039_${TIMESTAMP}.sql"

# ── Load .env if DATABASE_URL not already set ─────────────────────────────────
if [[ -z "${DATABASE_URL:-}" ]]; then
    ENV_FILE="${PROJECT_ROOT}/.env"
    if [[ -f "$ENV_FILE" ]]; then
        set -a
        # shellcheck disable=SC1090
        source "$ENV_FILE"
        set +a
    fi
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "ERROR: DATABASE_URL is not set. Set it in .env or as an environment variable."
    exit 1
fi

echo "=== ZASKA Migration 0039 Deployment ==="
echo "Timestamp: $TIMESTAMP"
echo "Database: ${DATABASE_URL%%@*}@[redacted]"
echo ""

# ── Step 1: Verify current migration state ───────────────────────────────────
echo "[1/5] Checking current Alembic revision..."
cd "$PROJECT_ROOT"
CURRENT_REV=$(alembic current 2>&1 | grep -oE '[0-9a-f]{12}' | head -1 || echo "unknown")
echo "      Current revision: $CURRENT_REV"

# ── Step 2: Backup ────────────────────────────────────────────────────────────
echo "[2/5] Creating pre-migration backup → $BACKUP_FILE"
pg_dump "$DATABASE_URL" \
    --no-password \
    --format=plain \
    --no-owner \
    --no-acl \
    > "$BACKUP_FILE"
echo "      Backup size: $(du -sh "$BACKUP_FILE" | cut -f1)"

# ── Step 3: Apply migration ───────────────────────────────────────────────────
echo "[3/5] Applying migration 0039..."
alembic upgrade 0039
echo "      Migration applied."

# ── Step 4: Post-deploy verification ─────────────────────────────────────────
echo "[4/5] Verifying schema..."

VERIFY_SQL=$(cat <<'SQL'
SELECT
    (SELECT COUNT(*) FROM information_schema.tables
     WHERE table_name IN (
        'trust_scores','badges','user_badges','skills',
        'user_skills','photo_verifications','moderation_cases'
     )) AS new_tables,
    (SELECT COUNT(*) FROM information_schema.columns
     WHERE table_name = 'users'
       AND column_name IN (
        'trust_score','is_suspended','ban_reason',
        'suspension_until','suspension_reason'
     )) AS new_user_cols;
SQL
)

RESULT=$(psql "$DATABASE_URL" --no-password --tuples-only --command "$VERIFY_SQL" 2>&1)
NEW_TABLES=$(echo "$RESULT" | tr -s ' ' | awk -F'|' '{print $1}' | tr -d ' ')
NEW_COLS=$(echo "$RESULT" | tr -s ' ' | awk -F'|' '{print $2}' | tr -d ' ')

if [[ "$NEW_TABLES" == "7" && "$NEW_COLS" == "5" ]]; then
    echo "      ✓ 7 new tables + 5 new user columns verified."
else
    echo "      ERROR: Expected 7 tables + 5 columns, got $NEW_TABLES tables + $NEW_COLS columns."
    echo "      Triggering automatic rollback..."
    alembic downgrade 0038
    echo "      Rolled back to 0038. Backup available at: $BACKUP_FILE"
    exit 1
fi

# ── Step 5: Seed trust catalog ────────────────────────────────────────────────
echo "[5/5] Seeding trust catalog (badges + skills)..."
cd "$PROJECT_ROOT"
python -c "
from app.db.session import SessionLocal
from app.services.trust_service import TrustService
db = SessionLocal()
try:
    TrustService(db).seed_catalog()
    print('      Trust catalog seeded successfully.')
finally:
    db.close()
"

echo ""
echo "=== Migration 0039 deployed successfully ==="
echo "Backup retained at: $BACKUP_FILE"
echo ""
echo "Rollback command (if needed):"
echo "  alembic downgrade 0038"
echo "  # OR: psql \"\$DATABASE_URL\" < $BACKUP_FILE"

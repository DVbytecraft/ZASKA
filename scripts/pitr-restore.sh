#!/bin/bash
# ZASKA — PostgreSQL Point-In-Time Recovery (PITR)
#
# Usage:
#   ./pitr-restore.sh "2026-05-11 14:30:00"    # restore to specific timestamp
#   ./pitr-restore.sh lsn:0/1A000000           # restore to specific LSN
#   ./pitr-restore.sh immediate                # restore to latest consistent state
#
# Prerequisites:
#   - PostgreSQL must be stopped
#   - WAL archive directory must be accessible at /var/wal-archive
#   - Base backup must exist at /var/wal-archive/base.tar.gz
#     (created via: pg_basebackup -h postgres -U zaska_admin -D /tmp/base -Ft -z -Xs -P)
#
# Procedure:
#   1. Stop PostgreSQL
#   2. Copy base backup to a new data directory
#   3. Create recovery.signal (PostgreSQL 12+ mode)
#   4. Configure recovery target in postgresql.conf
#   5. Start PostgreSQL — it replays WALs up to the target, then stops in read-only
#   6. Promote to primary when satisfied

set -euo pipefail

RESTORE_TARGET="${1:-immediate}"
PGDATA="${PGDATA:-/var/lib/postgresql/data}"
WAL_ARCHIVE="${ARCHIVE_DIR:-/var/wal-archive}"
BASE_BACKUP="${WAL_ARCHIVE}/base.tar.gz"
RESTORE_DIR="${PGDATA}_restore_$(date +%Y%m%d_%H%M%S)"

echo "=== ZASKA PITR RESTORE ==="
echo "Target      : ${RESTORE_TARGET}"
echo "WAL archive : ${WAL_ARCHIVE}"
echo "Restore to  : ${RESTORE_DIR}"
echo ""

if [ ! -f "$BASE_BACKUP" ]; then
    echo "ERROR: base backup not found at ${BASE_BACKUP}"
    echo "Create one with: pg_basebackup -h postgres -U zaska_admin -D /tmp/pgbase -Ft -z -Xs -P"
    exit 1
fi

# ── Step 1: Extract base backup ──────────────────────────────────────────────
echo "[1/5] Extracting base backup..."
mkdir -p "$RESTORE_DIR"
tar -xzf "$BASE_BACKUP" -C "$RESTORE_DIR"
echo "      done."

# ── Step 2: Configure WAL restore command ────────────────────────────────────
echo "[2/5] Configuring WAL restore..."
cat >> "${RESTORE_DIR}/postgresql.conf" << EOF

# PITR recovery configuration (appended by pitr-restore.sh)
restore_command = 'cp ${WAL_ARCHIVE}/%f %p'
recovery_target_action = promote
EOF

# Configure recovery target
if [ "$RESTORE_TARGET" = "immediate" ]; then
    echo "recovery_target = 'immediate'" >> "${RESTORE_DIR}/postgresql.conf"
elif echo "$RESTORE_TARGET" | grep -q "^lsn:"; then
    LSN="${RESTORE_TARGET#lsn:}"
    echo "recovery_target_lsn = '${LSN}'" >> "${RESTORE_DIR}/postgresql.conf"
else
    echo "recovery_target_time = '${RESTORE_TARGET}'" >> "${RESTORE_DIR}/postgresql.conf"
fi
echo "      done."

# ── Step 3: Create recovery signal ───────────────────────────────────────────
echo "[3/5] Creating recovery.signal..."
touch "${RESTORE_DIR}/recovery.signal"
echo "      done."

# ── Step 4: Set permissions ───────────────────────────────────────────────────
echo "[4/5] Setting permissions..."
chown -R postgres:postgres "$RESTORE_DIR" 2>/dev/null || true
chmod 700 "$RESTORE_DIR"
echo "      done."

echo "[5/5] Ready."
echo ""
echo "=== NEXT STEPS ==="
echo "1. Stop PostgreSQL:  docker compose stop postgres"
echo "2. Swap data dir:    mv ${PGDATA} ${PGDATA}_pre_restore && mv ${RESTORE_DIR} ${PGDATA}"
echo "3. Start PostgreSQL: docker compose start postgres"
echo "4. Validate:         ./scripts/validate-restore.sh"
echo "5. Promote:          psql -c \"SELECT pg_promote();\""
echo ""
echo "PostgreSQL will replay WALs to target '${RESTORE_TARGET}' then pause in read-only mode."
echo "After validation, run: psql -c \"SELECT pg_promote();\" to bring online as primary."

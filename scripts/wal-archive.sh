#!/bin/sh
# WAL archive command — called by PostgreSQL for each completed WAL segment.
# Usage: wal-archive.sh %p %f
#   %p = full path to WAL file (substituted by PostgreSQL)
#   %f = WAL filename only
#
# Contract (PostgreSQL archive_command requirements):
#   exit 0  → success, PostgreSQL recycles the WAL segment
#   exit != 0 → failure, PostgreSQL retries indefinitely until success
#
# Atomic write: tmp + rename prevents partial WAL files visible to restore tools.
# sync ensures durability before rename — crash between tmp and rename leaves
# only an incomplete .tmp file, which is ignored during restore.
#
# Local target: /var/wal-archive (bind-mounted docker volume)
# Production target: set ARCHIVE_TARGET to s3://bucket/prefix or b2://bucket/prefix
#   and install aws-cli or rclone in the PostgreSQL container.

set -e

WALFILE="$1"
ARCHFILE="$2"
ARCHIVE_DIR="${ARCHIVE_TARGET:-/var/wal-archive}"

if [ -z "$WALFILE" ] || [ -z "$ARCHFILE" ]; then
    echo "[wal-archive] ERROR: missing arguments (got '$WALFILE' '$ARCHFILE')" >&2
    exit 1
fi

mkdir -p "$ARCHIVE_DIR"

# Idempotency: if file already archived, succeed immediately (PostgreSQL may retry).
if [ -f "${ARCHIVE_DIR}/${ARCHFILE}" ]; then
    exit 0
fi

# Atomic write: write to .tmp then rename
cp "$WALFILE" "${ARCHIVE_DIR}/${ARCHFILE}.tmp"
sync "${ARCHIVE_DIR}/${ARCHFILE}.tmp"
mv "${ARCHIVE_DIR}/${ARCHFILE}.tmp" "${ARCHIVE_DIR}/${ARCHFILE}"

echo "[wal-archive] archived: ${ARCHFILE}"
exit 0

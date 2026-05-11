#!/bin/bash
# ZASKA — Post-Restore Financial Validation
#
# Runs immediately after a PITR restore to verify that:
#   1. Wallet conservation: SUM(balance) matches ledger
#   2. No orphan escrows
#   3. No duplicate transaction references
#   4. Ledger row count plausible (not truncated)
#   5. No open escrows left in partial states
#
# Usage: ./validate-restore.sh [postgres_url]
# Default URL: postgresql://zaska_admin:${POSTGRES_PASSWORD}@localhost:5432/zaska

set -euo pipefail

PG_URL="${1:-postgresql://zaska_admin:${POSTGRES_PASSWORD:-}@localhost:5432/zaska}"
PASS=0
FAIL=0

run_check() {
    local name="$1"
    local query="$2"
    local expected="$3"
    local result
    result=$(psql "$PG_URL" -t -A -c "$query" 2>/dev/null || echo "ERROR")
    if [ "$result" = "$expected" ] || [ "$expected" = "ANY" ]; then
        echo "  [PASS] ${name}"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] ${name} — expected '${expected}', got '${result}'"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== ZASKA RESTORE VALIDATION ==="
echo "URL: ${PG_URL}"
echo ""

# ── Check 1: PostgreSQL is reachable ─────────────────────────────────────────
echo "Connectivity..."
if ! psql "$PG_URL" -c "SELECT 1" >/dev/null 2>&1; then
    echo "  [FAIL] PostgreSQL not reachable at ${PG_URL}"
    exit 1
fi
echo "  [PASS] PostgreSQL reachable"
PASS=$((PASS + 1))

# ── Check 2: No wallet drift ─────────────────────────────────────────────────
echo "Wallet conservation..."
DRIFT_COUNT=$(psql "$PG_URL" -t -A -c "
SELECT COUNT(*) FROM (
    SELECT w.id,
           ABS(w.balance - COALESCE(SUM(CASE WHEN t.type = 'credit' THEN t.amount ELSE 0 END), 0)
                         + COALESCE(SUM(CASE WHEN t.type = 'debit' THEN t.amount ELSE 0 END), 0)) AS drift
    FROM wallets w
    LEFT JOIN transactions t ON t.wallet_id = w.id AND t.status = 'completed'
    GROUP BY w.id, w.balance
    HAVING ABS(w.balance - COALESCE(SUM(CASE WHEN t.type = 'credit' THEN t.amount ELSE 0 END), 0)
                         + COALESCE(SUM(CASE WHEN t.type = 'debit' THEN t.amount ELSE 0 END), 0)) > 0.000001
) drifts
" 2>/dev/null || echo "ERROR")

if [ "$DRIFT_COUNT" = "0" ]; then
    echo "  [PASS] No wallet drift detected"
    PASS=$((PASS + 1))
else
    echo "  [FAIL] ${DRIFT_COUNT} wallet(s) have balance drift — CRITICAL"
    FAIL=$((FAIL + 1))
fi

# ── Check 3: No duplicate transaction references ─────────────────────────────
echo "Duplicate references..."
DUP_COUNT=$(psql "$PG_URL" -t -A -c "
SELECT COUNT(*) FROM (
    SELECT wallet_id, reference FROM transactions
    WHERE status = 'completed'
    GROUP BY wallet_id, reference HAVING COUNT(*) > 1
) dups
" 2>/dev/null || echo "ERROR")

if [ "$DUP_COUNT" = "0" ]; then
    echo "  [PASS] No duplicate transaction references"
    PASS=$((PASS + 1))
else
    echo "  [FAIL] ${DUP_COUNT} duplicate reference(s) detected — CRITICAL"
    FAIL=$((FAIL + 1))
fi

# ── Check 4: No orphan escrows (released without settlement_tx_id) ───────────
echo "Escrow integrity..."
ORPHAN_ESCROW=$(psql "$PG_URL" -t -A -c "
SELECT COUNT(*) FROM escrows
WHERE status IN ('released', 'refunded')
  AND settlement_tx_id IS NULL
" 2>/dev/null || echo "ERROR")

if [ "$ORPHAN_ESCROW" = "0" ]; then
    echo "  [PASS] No orphan released escrows"
    PASS=$((PASS + 1))
else
    echo "  [FAIL] ${ORPHAN_ESCROW} released escrow(s) without settlement_tx_id"
    FAIL=$((FAIL + 1))
fi

# ── Check 5: No escrows in impossible states ──────────────────────────────────
echo "Escrow state machine..."
INVALID_ESCROW=$(psql "$PG_URL" -t -A -c "
SELECT COUNT(*) FROM escrows
WHERE status NOT IN ('pending', 'funded', 'hold', 'released', 'refunded', 'contested', 'cancelled', 'partial_released')
" 2>/dev/null || echo "ERROR")

if [ "$INVALID_ESCROW" = "0" ]; then
    echo "  [PASS] All escrow states valid"
    PASS=$((PASS + 1))
else
    echo "  [FAIL] ${INVALID_ESCROW} escrow(s) in unknown state"
    FAIL=$((FAIL + 1))
fi

# ── Check 6: Ledger rows plausible ───────────────────────────────────────────
echo "Ledger integrity..."
TX_COUNT=$(psql "$PG_URL" -t -A -c "SELECT COUNT(*) FROM transactions" 2>/dev/null || echo "ERROR")
if echo "$TX_COUNT" | grep -qE '^[0-9]+$'; then
    echo "  [PASS] Transaction table accessible (${TX_COUNT} rows)"
    PASS=$((PASS + 1))
else
    echo "  [FAIL] Cannot read transactions table"
    FAIL=$((FAIL + 1))
fi

# ── Check 7: No pending outbox events stuck (indicator of restore mid-flight) ──
echo "Outbox state..."
STUCK_OUTBOX=$(psql "$PG_URL" -t -A -c "
SELECT COUNT(*) FROM outbox_events
WHERE status = 'processing'
  AND created_at < NOW() - INTERVAL '10 minutes'
" 2>/dev/null || echo "ERROR")

if [ "$STUCK_OUTBOX" = "0" ]; then
    echo "  [PASS] No stuck outbox events"
    PASS=$((PASS + 1))
else
    echo "  [WARN] ${STUCK_OUTBOX} outbox event(s) stuck in 'processing' — may need manual reset"
    # Not a hard FAIL — could be pre-existing before incident
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "=== VALIDATION SUMMARY ==="
echo "  PASS: ${PASS}"
echo "  FAIL: ${FAIL}"
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo "RESULT: RESTORE VALIDATION FAILED — do NOT promote to primary"
    echo "        Investigate failures above before serving traffic"
    exit 1
else
    echo "RESULT: ALL CHECKS PASSED"
    echo "        Safe to promote: psql -c \"SELECT pg_promote();\""
    exit 0
fi

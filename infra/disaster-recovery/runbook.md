# ZASKA — Disaster Recovery Runbook

**Version:** 2026-05-11  
**RTO target:** 30 minutes  
**RPO target:** < 60 seconds (with WAL archiving)

---

## Prerequisites

```bash
# Required on the operator machine
psql, pg_basebackup, docker, docker compose

# Environment variables needed
POSTGRES_PASSWORD=<from vault>
PG_URL="postgresql://zaska_admin:${POSTGRES_PASSWORD}@localhost:5432/zaska"
```

---

## Scenario 1 — Pod crash / container restart

**Impact:** Transient, handled automatically by Docker/Kubernetes restart policy.

**Action:** None. Verify:
```bash
docker compose ps           # backend shows "Up"
curl http://localhost:6969/health/db
curl http://localhost:6969/health/redis
curl http://localhost:6969/health/scheduler
```

If scheduler shows dead jobs, restart:
```bash
docker compose restart backend
```

---

## Scenario 2 — PostgreSQL crash (data intact)

**Symptoms:** All API calls return 503, `/health/db` fails.  
**RTO:** 2–5 minutes.

```bash
# 1. Check container state
docker compose ps postgres

# 2. Restart PostgreSQL
docker compose restart postgres

# 3. Wait for healthy
docker compose exec postgres pg_isready -U zaska_admin -d zaska

# 4. Verify backend reconnects (pool_pre_ping handles stale connections)
curl http://localhost:6969/health/db

# 5. Check for any stuck outbox events
psql "$PG_URL" -c "UPDATE outbox_events SET status='pending' WHERE status='processing';"
```

---

## Scenario 3 — PITR: Logical corruption or accidental data loss

**Symptoms:** Wallet drift detected in reconciliation, escrows in impossible state,  
or confirmed accidental deletion.  
**RTO:** 15–30 minutes.  **RPO:** ≤ 60 seconds (archive_timeout=60).

### 3a — Create a fresh base backup (if none exists)
```bash
# Run this periodically (daily minimum) and store the result alongside WALs.
docker compose exec postgres \
  pg_basebackup -U zaska_admin -D /tmp/pgbase -Ft -z -Xs -P

# Copy to the WAL archive volume
docker compose cp postgres:/tmp/pgbase/base.tar.gz \
  /path/to/zaska-wal-archive/base.tar.gz
```

### 3b — Identify the restore target
```bash
# List archived WAL segments and find the timestamp before the incident
ls -lt /path/to/zaska-wal-archive/ | head -30

# For a specific table-level incident, use:
# SELECT pg_walfile_name(pg_current_wal_lsn());  ← run before incident
```

### 3c — Stop all services
```bash
docker compose stop backend celery_worker celery_beat pgbouncer
docker compose stop postgres
```

### 3d — Run PITR restore
```bash
# Restore to 2 minutes before the incident
./scripts/pitr-restore.sh "2026-05-11 14:28:00"

# Follow the printed instructions to swap directories
```

### 3e — Validate
```bash
POSTGRES_PASSWORD=<password> ./scripts/validate-restore.sh
# Must show: RESULT: ALL CHECKS PASSED
```

### 3f — Promote and restart
```bash
psql "$PG_URL" -c "SELECT pg_promote();"
docker compose start pgbouncer backend celery_worker celery_beat
curl http://localhost:6969/health/db
```

### 3g — Reset stuck outbox events
```bash
psql "$PG_URL" -c "UPDATE outbox_events SET status='pending', next_attempt_at=NOW() WHERE status='processing';"
```

---

## Scenario 4 — Redis failure

**Impact:** Degraded mode — auth still works (fail-open), rate limiting disabled,  
scheduler locks lost (jobs may run concurrently for one cycle), WS tickets fail.

**RTO:** 30 seconds (Docker restart) to 5 minutes (Sentinel failover).

```bash
# 1. Check Redis
docker compose ps redis
docker compose exec redis redis-cli ping

# 2. Restart Redis (data is volatile by design — no persistence)
docker compose restart redis

# 3. Verify
curl http://localhost:6969/health/redis

# 4. Reset scheduler heartbeats (watchdog will re-populate within 5 min)
# No action needed — scheduler auto-restarts jobs after Redis reconnect.

# 5. Force re-issue WS tickets for active sessions
# Users will see a brief disconnect on next WS operation — they reconnect automatically.
```

**Note:** Redis holds no financial state. All financial data lives in PostgreSQL.  
Redis failure never causes money loss, only degraded UX.

---

## Scenario 5 — Rolling deploy during active WebRTC calls

**Impact:** Calls in-flight when a pod is replaced may lose signaling.

**Behavior with current architecture:**
- preStop hook gives 5s for LB drain
- graceful shutdown gives 30s for connections to close
- ICE restart logic retries for 8s on disconnect
- Redis signal queue ensures offer/answer survive pod restart

**Expected outcome:** ~10% of calls in mid-negotiation phase will reconnect within 8s.  
Established calls (ICE connected) will ICE-restart and recover.

**If calls are not recovering:**
```bash
# Check signaling queue length
docker compose exec redis redis-cli KEYS "signaling:*" | wc -l

# Drain stuck queues older than 2 minutes
docker compose exec redis redis-cli KEYS "signaling:queue:*" | \
  xargs -I{} redis-cli TTL {} | grep -v "^-"
```

---

## Scenario 6 — PgBouncer failure

**Impact:** All API calls fail (backend cannot connect to DB).  
**RTO:** 30 seconds.

```bash
# 1. Restart PgBouncer
docker compose restart pgbouncer

# 2. If PgBouncer is broken, temporary bypass (scale-down to 1 pod only)
# Edit docker-compose.yml: DATABASE_URL → postgres:5432 directly
# Set DB_POOL_SIZE=10, DB_MAX_OVERFLOW=20
# docker compose up -d backend

# 3. Verify
curl http://localhost:6969/health/db
```

---

## Financial validation after ANY incident

**Always run before declaring recovery complete:**
```bash
POSTGRES_PASSWORD=<password> ./scripts/validate-restore.sh

# Also check reconciliation
curl http://localhost:6969/health/scheduler
psql "$PG_URL" -t -c "SELECT COUNT(*) FROM outbox_events WHERE status='dead_letter';"
psql "$PG_URL" -t -c "SELECT COUNT(*) FROM escrows WHERE status='hold' AND payout_available_at < NOW() - INTERVAL '15 minutes';"
```

**Recovery is NOT complete until validate-restore.sh returns exit 0.**

---

## Contacts & Escalation

| Severity | Condition | Action |
|----------|-----------|--------|
| P0 | Wallet drift > 0 | Immediate — freeze payments, escalate |
| P0 | Duplicate transaction references | Immediate — freeze payments, escalate |
| P1 | PostgreSQL down > 5 minutes | Page on-call SRE |
| P1 | Scheduler silent > 15 minutes | Check + restart scheduler |
| P2 | Redis down > 2 minutes | Restart Redis |
| P2 | PgBouncer connection refusals | Restart PgBouncer |

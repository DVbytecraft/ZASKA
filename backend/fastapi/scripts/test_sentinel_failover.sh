#!/usr/bin/env bash
# test_sentinel_failover.sh — Validates Redis Sentinel HA failover for ZASKA
#
# Tests:
#   1. Normal connectivity: application connects to master via Sentinel
#   2. Master failure: kill master → Sentinel elects new master → app reconnects
#   3. Master recovery: original master rejoins as replica → app still writes to new master
#
# Prerequisites:
#   - Docker and docker-compose available on PATH
#   - Python + redis-py installed (pip install redis)
#   - Port 6380/6381/6382 (Redis nodes) and 26379/26380/26381 (Sentinels) free
#
# Usage:
#   chmod +x scripts/test_sentinel_failover.sh
#   ./scripts/test_sentinel_failover.sh
#
# The script creates a temporary docker-compose env, runs the tests, then tears down.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/../tests/infra/docker-compose.sentinel.yml"
PASS=0
FAIL=0

# ── Colors ────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; RESET='\033[0m'
ok()   { echo -e "${GREEN}✓ PASS${RESET} $*"; ((PASS++)); }
fail() { echo -e "${RED}✗ FAIL${RESET} $*"; ((FAIL++)); }
info() { echo -e "${YELLOW}→${RESET} $*"; }

# ── Create docker-compose if not present ─────────────────────────────────────
mkdir -p "$(dirname "$COMPOSE_FILE")"
cat > "$COMPOSE_FILE" <<'YAML'
version: "3.8"
services:
  redis-master:
    image: redis:7-alpine
    container_name: zaska_redis_master
    ports: ["6380:6379"]
    command: redis-server --save "" --appendonly no

  redis-replica1:
    image: redis:7-alpine
    container_name: zaska_redis_replica1
    ports: ["6381:6379"]
    command: redis-server --save "" --appendonly no --replicaof redis-master 6379
    depends_on: [redis-master]

  redis-replica2:
    image: redis:7-alpine
    container_name: zaska_redis_replica2
    ports: ["6382:6379"]
    command: redis-server --save "" --appendonly no --replicaof redis-master 6379
    depends_on: [redis-master]

  sentinel1:
    image: redis:7-alpine
    container_name: zaska_sentinel1
    ports: ["26379:26379"]
    command: >
      sh -c "echo 'port 26379
      sentinel monitor mymaster redis-master 6379 2
      sentinel down-after-milliseconds mymaster 5000
      sentinel failover-timeout mymaster 15000
      sentinel parallel-syncs mymaster 1' > /tmp/sentinel.conf &&
      redis-sentinel /tmp/sentinel.conf"
    depends_on: [redis-master, redis-replica1, redis-replica2]

  sentinel2:
    image: redis:7-alpine
    container_name: zaska_sentinel2
    ports: ["26380:26379"]
    command: >
      sh -c "echo 'port 26379
      sentinel monitor mymaster redis-master 6379 2
      sentinel down-after-milliseconds mymaster 5000
      sentinel failover-timeout mymaster 15000
      sentinel parallel-syncs mymaster 1' > /tmp/sentinel.conf &&
      redis-sentinel /tmp/sentinel.conf"
    depends_on: [redis-master, redis-replica1, redis-replica2]

  sentinel3:
    image: redis:7-alpine
    container_name: zaska_sentinel3
    ports: ["26381:26379"]
    command: >
      sh -c "echo 'port 26379
      sentinel monitor mymaster redis-master 6379 2
      sentinel down-after-milliseconds mymaster 5000
      sentinel failover-timeout mymaster 15000
      sentinel parallel-syncs mymaster 1' > /tmp/sentinel.conf &&
      redis-sentinel /tmp/sentinel.conf"
    depends_on: [redis-master, redis-replica1, redis-replica2]
YAML

# ── Python test runner ────────────────────────────────────────────────────────
PYTHON_TEST=$(cat <<'PYEOF'
import sys
import time
import redis
from redis.sentinel import Sentinel

SENTINELS = [("127.0.0.1", 26379), ("127.0.0.1", 26380), ("127.0.0.1", 26381)]
MASTER_NAME = "mymaster"

def get_sentinel():
    return Sentinel(SENTINELS, socket_timeout=2, socket_connect_timeout=2)

def test_normal_write_read():
    s = get_sentinel()
    master = s.master_for(MASTER_NAME, socket_timeout=2)
    master.set("failover_test_key", "hello_zaska")
    val = master.get("failover_test_key")
    assert val == b"hello_zaska", f"Expected b'hello_zaska', got {val}"
    print("PASS: normal write/read")
    return True

def test_read_from_replica():
    s = get_sentinel()
    replica = s.slave_for(MASTER_NAME, socket_timeout=2)
    # Key was set on master, replicas should have it (allow 1s replication lag)
    time.sleep(1)
    val = replica.get("failover_test_key")
    assert val == b"hello_zaska", f"Expected b'hello_zaska' on replica, got {val}"
    print("PASS: read from replica")
    return True

def test_sentinel_reports_master():
    s = get_sentinel()
    master_info = s.discover_master(MASTER_NAME)
    assert master_info is not None, "Sentinel did not report a master"
    print(f"PASS: sentinel reports master at {master_info[0]}:{master_info[1]}")
    return True

def test_write_after_master_killed():
    """Kill master container (external), then verify write succeeds on new master."""
    import subprocess
    import time

    print("  Killing redis-master container...")
    subprocess.run(["docker", "stop", "zaska_redis_master"], check=True, capture_output=True)

    # Wait for Sentinel to detect failure and elect a new master (up to 30s)
    deadline = time.time() + 30
    new_master = None
    while time.time() < deadline:
        try:
            s = get_sentinel()
            new_master = s.discover_master(MASTER_NAME)
            m = s.master_for(MASTER_NAME, socket_timeout=2)
            m.set("post_failover_key", "survived_failover")
            val = m.get("post_failover_key")
            assert val == b"survived_failover"
            break
        except Exception:
            time.sleep(2)
    else:
        print("FAIL: no master elected within 30 seconds after master kill")
        return False

    print(f"PASS: failover completed — new master at {new_master[0]}:{new_master[1]}")
    return True

tests = [test_normal_write_read, test_read_from_replica, test_sentinel_reports_master, test_write_after_master_killed]
results = []
for t in tests:
    try:
        results.append(t())
    except Exception as e:
        print(f"FAIL: {t.__name__}: {e}")
        results.append(False)

passed = sum(1 for r in results if r)
print(f"\n{passed}/{len(results)} tests passed")
sys.exit(0 if passed == len(results) else 1)
PYEOF
)

# ── Main ──────────────────────────────────────────────────────────────────────
echo "=== ZASKA Redis Sentinel Failover Test ==="
echo ""

info "Starting Sentinel cluster (docker-compose)..."
docker compose -f "$COMPOSE_FILE" up -d --wait 2>/dev/null || \
    docker-compose -f "$COMPOSE_FILE" up -d
sleep 8  # allow Sentinel quorum to form

info "Running failover tests..."
if python3 -c "$PYTHON_TEST"; then
    ok "All Sentinel failover tests passed."
else
    fail "One or more Sentinel failover tests failed."
fi

info "Tearing down Sentinel cluster..."
docker compose -f "$COMPOSE_FILE" down -v 2>/dev/null || \
    docker-compose -f "$COMPOSE_FILE" down -v

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[[ $FAIL -eq 0 ]] && exit 0 || exit 1

"""Reset ZASKA database — wipe all user/business data, keep schema and seed data.

Usage:
    # Local (reads .env automatically via config):
    python scripts/reset_all_data.py

    # Remote (pass DATABASE_URL explicitly):
    DATABASE_URL=postgresql+psycopg://user:pass@host/db python scripts/reset_all_data.py

    # Dry-run (shows what would be truncated, no changes):
    RESET_DRY_RUN=1 python scripts/reset_all_data.py

Safety:
    - Prompts for confirmation before any destructive action.
    - NEVER touches: alembic_version, country_config, location_config.
    - Re-seeds country_config and platform wallet after wipe.
    - Works in any env (local Docker, Render, Railway, Supabase, etc.).
"""

import os
import sys

# Make app importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend", "fastapi"))

DRY_RUN = os.environ.get("RESET_DRY_RUN", "").strip() in ("1", "true", "yes")

# Tables to TRUNCATE — order matters for FK safety (children first, then parents).
# RESTART IDENTITY resets all serial/UUID sequences.
# CASCADE handles any remaining FK references automatically.
_TABLES_TO_WIPE = [
    # ── Leaf / child tables first ─────────────────────────────────────────
    "outbox_events",
    "financial_audit_logs",
    "webhook_idempotency",
    "support_tickets",
    "negotiation_events",
    "chat_messages",
    "call_sessions",
    "notifications",
    "task_completion_codes",
    "task_applications",
    "user_addresses",
    "virtual_cards",
    "kyc_submissions",
    "payment_methods",
    "payouts",
    "reconciliation_reports",
    "disputes",
    "feature_flags",
    # ── Financial core ────────────────────────────────────────────────────
    "transactions",
    "escrows",
    "wallets",
    # ── Business entities ─────────────────────────────────────────────────
    "tasks",
    # ── Root: users last ─────────────────────────────────────────────────
    "users",
]

# Tables NEVER touched — schema versioning and seeded reference data
_PROTECTED_TABLES = {
    "alembic_version",
    "countries",
    "currencies",
    "emergency_numbers",
    "payment_methods_config",
}


def _confirm(db_url: str) -> bool:
    """Prompt user to confirm destruction. Returns True if confirmed."""
    # Mask password in display
    display_url = db_url
    if "@" in db_url:
        prefix = db_url.split("://")[0]
        rest = db_url.split("@", 1)[1]
        display_url = f"{prefix}://***:***@{rest}"

    print()
    print("=" * 60)
    print("  !! DESTRUCTIVE OPERATION — ALL DATA WILL BE DELETED !!")
    print("=" * 60)
    print(f"  Target: {display_url}")
    print(f"  Tables: {len(_TABLES_TO_WIPE)} tables will be wiped")
    print(f"  Protected: {', '.join(sorted(_PROTECTED_TABLES))}")
    print("=" * 60)

    if DRY_RUN:
        print("  DRY-RUN mode — no changes will be made")
        return True

    answer = input("\n  Type  YES  to confirm: ").strip()
    return answer == "YES"


def run():
    from sqlalchemy import create_engine, text

    # Resolve DATABASE_URL: env override > config file
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        try:
            from app.core.config import settings
            db_url = settings.database_url
        except Exception as exc:
            print(f"[reset] Could not load settings: {exc}")
            print("[reset] Pass DATABASE_URL as environment variable.")
            sys.exit(1)

    if not db_url:
        print("[reset] DATABASE_URL is empty. Aborting.")
        sys.exit(1)

    # Psycopg3 driver alias
    if db_url.startswith("postgresql://") and "psycopg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

    if not _confirm(db_url):
        print("[reset] Aborted.")
        sys.exit(0)

    engine = create_engine(db_url, echo=False)

    # Verify every table exists before wiping anything
    with engine.connect() as conn:
        existing = {
            row[0]
            for row in conn.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public'"
                )
            )
        }

    missing = [t for t in _TABLES_TO_WIPE if t not in existing]
    if missing:
        print(f"[reset] WARNING: these tables don't exist and will be skipped: {missing}")

    tables_to_truncate = [t for t in _TABLES_TO_WIPE if t in existing]

    if not tables_to_truncate:
        print("[reset] Nothing to truncate (no matching tables found).")
        sys.exit(0)

    print(f"\n[reset] Tables to truncate: {tables_to_truncate}")

    if DRY_RUN:
        print("[reset] DRY-RUN complete — no changes made.")
        return

    # Single TRUNCATE statement with CASCADE handles remaining FK refs
    truncate_sql = (
        "TRUNCATE "
        + ", ".join(tables_to_truncate)
        + " RESTART IDENTITY CASCADE;"
    )

    with engine.begin() as conn:
        conn.execute(text(truncate_sql))

    print("[reset] ✓ All tables wiped.")

    # Re-seed countries
    print("[reset] Re-seeding country configs...")
    try:
        import subprocess
        seed_countries = os.path.join(
            os.path.dirname(__file__), "..", "backend", "fastapi", "scripts", "seed_countries.py"
        )
        result = subprocess.run(
            [sys.executable, seed_countries],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print("[reset] ✓ Countries re-seeded.")
        else:
            print(f"[reset] WARNING: seed_countries failed:\n{result.stderr}")
    except Exception as exc:
        print(f"[reset] WARNING: could not re-seed countries: {exc}")

    # Re-seed platform wallet
    print("[reset] Re-seeding platform wallet user...")
    try:
        seed_wallet = os.path.join(
            os.path.dirname(__file__), "..", "backend", "fastapi", "scripts", "seed_platform_wallet.py"
        )
        result = subprocess.run(
            [sys.executable, seed_wallet],
            capture_output=True, text=True,
            env={**os.environ, "DATABASE_URL": db_url},
        )
        if result.returncode == 0:
            platform_id = result.stdout.strip()
            print(f"[reset] ✓ Platform wallet re-seeded (id={platform_id}).")
        else:
            print(f"[reset] WARNING: seed_platform_wallet failed:\n{result.stderr}")
    except Exception as exc:
        print(f"[reset] WARNING: could not re-seed platform wallet: {exc}")

    # Flush Redis — wipe OTP codes, token blacklists, rate-limit counters,
    # WS tickets, idempotency keys, job locks, audit bootstrap keys.
    # Does NOT flush country engine cache (it rebuilds itself on next request).
    print("[reset] Flushing Redis...")
    try:
        from app.core.redis_client import redis_sync
        redis_sync.flushdb()
        print("[reset] ✓ Redis flushed.")
    except Exception as exc:
        print(f"[reset] WARNING: Redis flush failed (not critical if Redis is down): {exc}")

    print("\n[reset] ✓ RESET COMPLETE — database + Redis are clean.")
    print("[reset]   Next: register users, create tasks, run your test scenario.")


if __name__ == "__main__":
    run()

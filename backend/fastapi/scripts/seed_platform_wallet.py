"""Seed the ZASKA platform wallet user.

Creates a system user account that receives all platform commissions (15% of
each escrow release).  This script is idempotent — safe to run multiple times.

Usage (from docker-entrypoint.sh):
    PLATFORM_USER_ID=$(python seed_platform_wallet.py)
    export ZASKA_WALLET_USER_ID="${ZASKA_WALLET_USER_ID:-$PLATFORM_USER_ID}"

The script prints ONLY the user_id to stdout on success (no other output),
so the shell assignment works correctly.  All diagnostic messages go to stderr.
"""

import sys

# Ensure app is importable
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run() -> str:
    """Create or retrieve the platform wallet user. Returns the user_id."""
    from app.db.session import SessionLocal
    from app.services.internal_wallet_seed_service import InternalWalletSeedService

    db = SessionLocal()
    try:
        exports = InternalWalletSeedService(db).ensure_all()
        return exports["ZASKA_WALLET_USER_ID"]
    finally:
        db.close()


if __name__ == "__main__":
    user_id = run()
    # Print ONLY the user_id to stdout — nothing else
    # The entrypoint captures this with: PLATFORM_USER_ID=$(python seed_platform_wallet.py)
    print(user_id)

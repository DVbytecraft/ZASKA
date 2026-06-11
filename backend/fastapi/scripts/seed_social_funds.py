"""Seed the ZASKA social fund wallet users.

Creates or retrieves the internal users backing:
- pension fund
- health fund
- smoothing fund

The script is idempotent and prints shell-friendly KEY=VALUE lines to stdout:

    PENSION_FUND_USER_ID=<uuid>
    HEALTH_FUND_USER_ID=<uuid>
    SMOOTHING_FUND_USER_ID=<uuid>
"""

from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run() -> dict[str, str]:
    from app.core.observability.logger import redirect_to_stderr
    redirect_to_stderr()

    from app.db.session import SessionLocal
    from app.services.internal_wallet_seed_service import InternalWalletSeedService

    db = SessionLocal()
    try:
        return {
            key: value
            for key, value in InternalWalletSeedService(db).ensure_all().items()
            if key in {"PENSION_FUND_USER_ID", "HEALTH_FUND_USER_ID", "SMOOTHING_FUND_USER_ID"}
        }
    finally:
        db.close()


if __name__ == "__main__":
    seeded = run()
    for key, value in seeded.items():
        print(f"{key}={value}")

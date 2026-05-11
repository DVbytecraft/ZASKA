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
import uuid
from decimal import Decimal

# Ensure app is importable
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Well-known internal identity for the platform wallet user.
# This email is never sent real messages — it is a system account.
_PLATFORM_EMAIL = "zaska-platform@internal.zaska"
_PLATFORM_PHONE = "+00000000000"
_PLATFORM_NAME = "ZASKA Platform"

# All currencies the platform may receive commissions in
_PLATFORM_CURRENCIES = ["USD", "XOF", "XAF", "GHS", "NGN", "KES", "EUR"]


def run() -> str:
    """Create or retrieve the platform wallet user. Returns the user_id."""
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError

    from app.db.session import SessionLocal
    from app.models.user import User
    from app.models.wallet import Wallet

    db = SessionLocal()
    try:
        # Check if platform user already exists
        user = db.execute(
            select(User).where(User.email == _PLATFORM_EMAIL)
        ).scalars().one_or_none()

        if user is None:
            print("[seed_platform_wallet] Creating platform wallet user...", file=sys.stderr)
            user = User(
                id=str(uuid.uuid4()),
                email=_PLATFORM_EMAIL,
                phone=_PLATFORM_PHONE,
                first_name="ZASKA",
                last_name="Platform",
                full_name=_PLATFORM_NAME,
                password_hash=None,        # system account — no login possible
                role="client",             # minimal privileges — receives credits only
                is_verified=True,          # no OTP needed for system accounts
                country_code="TG",
            )
            db.add(user)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                # Concurrent startup — another instance won the race, fetch their result
                user = db.execute(
                    select(User).where(User.email == _PLATFORM_EMAIL)
                ).scalars().one()
                print(f"[seed_platform_wallet] Already exists (id={user.id})", file=sys.stderr)
                return user.id

        # Ensure wallets exist for all platform currencies
        created_currencies = []
        for currency in _PLATFORM_CURRENCIES:
            existing = db.execute(
                select(Wallet).where(
                    Wallet.user_id == user.id,
                    Wallet.currency == currency,
                )
            ).scalars().one_or_none()
            if existing is None:
                db.add(Wallet(
                    user_id=user.id,
                    currency=currency,
                    balance=Decimal("0"),
                ))
                created_currencies.append(currency)

        db.commit()

        if created_currencies:
            print(
                f"[seed_platform_wallet] Created wallets: {created_currencies}",
                file=sys.stderr,
            )
        else:
            print(
                f"[seed_platform_wallet] Platform user already complete (id={user.id})",
                file=sys.stderr,
            )

        return user.id

    finally:
        db.close()


if __name__ == "__main__":
    user_id = run()
    # Print ONLY the user_id to stdout — nothing else
    # The entrypoint captures this with: PLATFORM_USER_ID=$(python seed_platform_wallet.py)
    print(user_id)

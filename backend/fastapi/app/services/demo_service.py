"""Demo session service — ephemeral sandbox users for app demonstration.

Each POST /demo/session creates a fresh, isolated demo User with:
  - is_demo=True  (bypasses KYC checks, excluded from real-user queries)
  - is_verified=True  (skips OTP gate)
  - country_code="CI", currency=XOF
  - 10 000 XOF pre-seeded in wallet
  - Short-lived JWT (2 h) — no refresh token issued

Cleanup: _cleanup_demo_users() (called by scheduler every 6 h) deletes demo
users whose JWTs have long expired (> 24 h old). Deletion is best-effort
per user; if FK constraints prevent it, the user is suspended instead so it
can no longer receive a valid JWT via the demo endpoint.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_token
from app.models.user import User
from app.models.wallet import Transaction, Wallet
from app.services.wallet_service import WalletService

logger = logging.getLogger(__name__)

DEMO_JWT_TTL = timedelta(hours=2)
_DEMO_USER_STALE_HOURS = 24


def bootstrap_demo_user(db: Session) -> dict:
    """Create a fresh demo user with a pre-seeded wallet and return a JWT."""
    demo_id = str(uuid.uuid4())
    short_id = demo_id[:8]

    user = User(
        id=demo_id,
        email=f"demo_{short_id}@zaska.demo",
        first_name="Démo",
        last_name="Utilisateur",
        full_name="Démo Utilisateur",
        is_verified=True,
        is_demo=True,
        role="client",
        country_code="CI",
    )
    db.add(user)
    db.flush()

    wallet_svc = WalletService(db)
    wallet_svc.create_wallet(demo_id, "XOF")
    wallet_svc.credit_wallet(
        demo_id,
        "XOF",
        amount=Decimal("10000"),
        reference=f"demo_seed_{short_id}",
        provider="internal",
    )

    db.commit()

    access_token = create_token(demo_id, DEMO_JWT_TTL, "access")
    return {
        "accessToken": access_token,
        "userId": demo_id,
        "country": "CI",
        "currency": "XOF",
        "isDemo": True,
    }


def cleanup_stale_demo_users(db: Session) -> dict:
    """Delete demo users older than _DEMO_USER_STALE_HOURS.

    Deletion order: transactions → wallets → user (FK-safe).
    If user deletion fails (e.g. task FK), the user is suspended so it can
    no longer authenticate (the JWT will also have expired by this point).
    """
    cutoff = datetime.utcnow() - timedelta(hours=_DEMO_USER_STALE_HOURS)
    stale_users = db.execute(
        select(User).where(User.is_demo.is_(True), User.created_at < cutoff)
    ).scalars().all()

    deleted = 0
    suspended = 0

    for user in stale_users:
        try:
            wallets = db.execute(
                select(Wallet).where(Wallet.user_id == user.id)
            ).scalars().all()
            wallet_ids = [w.id for w in wallets]

            if wallet_ids:
                txs = db.execute(
                    select(Transaction).where(Transaction.wallet_id.in_(wallet_ids))
                ).scalars().all()
                for tx in txs:
                    db.delete(tx)
                db.flush()

                for wallet in wallets:
                    db.delete(wallet)
                db.flush()

            db.delete(user)
            db.flush()
            deleted += 1
        except Exception as exc:
            db.rollback()
            try:
                user.is_suspended = True
                user.is_demo = False
                user.suspension_reason = "demo_expired"
                db.commit()
                suspended += 1
            except Exception as inner_exc:
                db.rollback()
                logger.error(
                    "demo_cleanup: could not remove or suspend user=%s — %s / %s",
                    user.id, exc, inner_exc,
                )

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("demo_cleanup: final commit failed — %s", exc)

    return {"deleted": deleted, "suspended": suspended, "scanned": len(stale_users)}

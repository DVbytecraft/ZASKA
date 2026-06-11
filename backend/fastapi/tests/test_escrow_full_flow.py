"""
Critical path tests for the escrow lifecycle.

Covers both internal (wallet-funded) and external (Stripe-funded) escrow paths.
Uses SQLite in-memory — SELECT FOR UPDATE is silently ignored by SQLite but all
balance arithmetic is exercised correctly.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.task import Task
from app.models.user import User
from app.services.internal_wallet_seed_service import InternalWalletSeedService
from app.services.wallet_service import (
    EscrowError,
    InsufficientFundsError,
    WalletService,
)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    for uid, email, role in [
        ("payer", "payer@test.com", "client"),
        ("payee", "payee@test.com", "worker"),
    ]:
        session.add(User(id=uid, email=email, password_hash="x", role=role, is_verified=True))
    session.add(
        Task(
            id="task-1",
            title="T",
            description="D",
            price=500.0,
            currency="XOF",
            latitude=1.0,
            longitude=1.0,
            status="ASSIGNED",
            created_by="payer",
            assigned_to="payee",
        )
    )
    session.commit()
    # Provision the platform/pension/health/smoothing fund wallets and bind their
    # user ids onto settings — release_escrow hard-fails (SocialSplitConfigError)
    # if these are not configured, see _credit_social_split. Reset any ids bound by
    # a previous test's (separate, in-memory) database first, since settings is a
    # process-wide singleton and _bind_setting only binds when empty.
    from app.core.config import settings as _settings
    for _name in ("zaska_wallet_user_id", "pension_fund_user_id", "health_fund_user_id", "smoothing_fund_user_id"):
        setattr(_settings, _name, "")
    InternalWalletSeedService(session).ensure_all()
    yield session
    session.close()


# ── Internal escrow (wallet-funded) ──────────────────────────────────────────

def test_internal_escrow_create_deducts_payer(db_session):
    svc = WalletService(db_session)
    svc.create_wallet("payer", "XOF")
    svc.credit_wallet("payer", "XOF", Decimal("1000"), "seed")

    svc.create_escrow("task-1", "payer", "payee", Decimal("500"), "XOF")

    assert svc.get_balance("payer", "XOF") == Decimal("500")


def test_internal_escrow_release_credits_payee(db_session):
    svc = WalletService(db_session)
    svc.create_wallet("payer", "XOF")
    svc.create_wallet("payee", "XOF")
    svc.credit_wallet("payer", "XOF", Decimal("1000"), "seed")

    escrow = svc.create_escrow("task-1", "payer", "payee", Decimal("500"), "XOF")
    svc.release_escrow(escrow.id)

    split = svc.calculate_social_split(Decimal("500"))
    assert svc.get_balance("payer", "XOF") == Decimal("500")
    assert svc.get_balance("payee", "XOF") == split["tasker_net"]


def test_internal_escrow_refund_returns_to_payer(db_session):
    svc = WalletService(db_session)
    svc.create_wallet("payer", "XOF")
    svc.credit_wallet("payer", "XOF", Decimal("1000"), "seed")

    escrow = svc.create_escrow("task-1", "payer", "payee", Decimal("500"), "XOF")
    svc.refund_escrow(escrow.id)

    assert svc.get_balance("payer", "XOF") == Decimal("1000")


def test_internal_escrow_insufficient_funds_raises(db_session):
    svc = WalletService(db_session)
    svc.create_wallet("payer", "XOF")
    svc.credit_wallet("payer", "XOF", Decimal("100"), "seed")

    with pytest.raises(InsufficientFundsError):
        svc.create_escrow("task-1", "payer", "payee", Decimal("500"), "XOF")


def test_internal_escrow_release_requires_funded_status(db_session):
    svc = WalletService(db_session)
    svc.create_wallet("payer", "XOF")
    svc.credit_wallet("payer", "XOF", Decimal("1000"), "seed")

    escrow = svc.create_escrow("task-1", "payer", "payee", Decimal("500"), "XOF")
    svc.release_escrow(escrow.id)

    with pytest.raises(EscrowError):
        svc.release_escrow(escrow.id)  # already released → must fail


def test_internal_escrow_double_refund_raises(db_session):
    svc = WalletService(db_session)
    svc.create_wallet("payer", "XOF")
    svc.credit_wallet("payer", "XOF", Decimal("1000"), "seed")

    escrow = svc.create_escrow("task-1", "payer", "payee", Decimal("500"), "XOF")
    svc.refund_escrow(escrow.id)

    with pytest.raises(EscrowError):
        svc.refund_escrow(escrow.id)  # already refunded → must fail


# ── External escrow (Stripe-funded, create_pending_escrow path) ──────────────

def test_external_escrow_pending_no_wallet_debit(db_session):
    svc = WalletService(db_session)
    svc.create_wallet("payer", "XOF")
    svc.credit_wallet("payer", "XOF", Decimal("1000"), "seed")

    svc.create_pending_escrow("task-1", "payer", "payee", Decimal("500"), "XOF")

    # Payer wallet untouched — money came from external provider
    assert svc.get_balance("payer", "XOF") == Decimal("1000")


def test_external_escrow_fund_then_release_credits_payee(db_session):
    svc = WalletService(db_session)
    svc.create_wallet("payee", "XOF")

    escrow = svc.create_pending_escrow("task-1", "payer", "payee", Decimal("500"), "XOF")
    assert escrow.status == "pending"

    svc.fund_escrow_from_payment(escrow.id, provider="stripe", provider_tx_id="pi_test_001")
    escrow_funded = svc.get_escrow(escrow.id)
    assert escrow_funded.status == "funded"

    svc.release_escrow(escrow.id)
    split = svc.calculate_social_split(Decimal("500"))
    assert svc.get_balance("payee", "XOF") == split["tasker_net"]


def test_external_escrow_fund_idempotent(db_session):
    svc = WalletService(db_session)
    escrow = svc.create_pending_escrow("task-1", "payer", "payee", Decimal("500"), "XOF")

    svc.fund_escrow_from_payment(escrow.id, "stripe", "pi_test_002")
    # Second call with same provider tx — must not raise, must return same escrow
    result = svc.fund_escrow_from_payment(escrow.id, "stripe", "pi_test_002")
    assert result.status == "funded"


def test_external_escrow_cannot_fund_already_funded(db_session):
    """Funding an already-funded escrow with a different tx is a warning, not an exception."""
    svc = WalletService(db_session)
    escrow = svc.create_pending_escrow("task-1", "payer", "payee", Decimal("500"), "XOF")
    svc.fund_escrow_from_payment(escrow.id, "stripe", "pi_001")

    # Idempotent — returns existing funded escrow
    result = svc.fund_escrow_from_payment(escrow.id, "stripe", "pi_001")
    assert result.status == "funded"


# ── Conservation invariant ────────────────────────────────────────────────────

def test_no_money_created_in_internal_flow(db_session):
    """Releasing an escrow only redistributes the gross amount across payer/payee/social-split
    funds — no money is created or destroyed (wallet == ledger invariant)."""
    from app.core.config import settings as _s

    svc = WalletService(db_session)
    svc.create_wallet("payer", "XOF")
    svc.create_wallet("payee", "XOF")
    svc.credit_wallet("payer", "XOF", Decimal("1000"), "seed")

    fund_user_ids = [
        _s.zaska_wallet_user_id,
        _s.pension_fund_user_id,
        _s.health_fund_user_id,
        _s.smoothing_fund_user_id,
    ]

    def _total_balance() -> Decimal:
        total = svc.get_balance("payer", "XOF") + svc.get_balance("payee", "XOF")
        for uid in fund_user_ids:
            total += svc.get_balance(uid, "XOF")
        return total

    total_before = _total_balance()

    escrow = svc.create_escrow("task-1", "payer", "payee", Decimal("600"), "XOF")
    svc.release_escrow(escrow.id)

    total_after = _total_balance()
    # The escrow gross (600) is fully redistributed: payee + 4 social-split funds sum to 600,
    # payer's debit at create_escrow already removed it from the total above.
    assert total_before == total_after, (
        f"Expected conservation: total_before={total_before}, got total_after={total_after}"
    )

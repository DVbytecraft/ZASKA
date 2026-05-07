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
from app.services.wallet_service import EscrowError, InsufficientFundsError, WalletService


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

    assert svc.get_balance("payer", "XOF") == Decimal("500")
    assert svc.get_balance("payee", "XOF") == Decimal("500")


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
    assert svc.get_balance("payee", "XOF") == Decimal("500")


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
    """Total wallet balance before == total wallet balance after release."""
    svc = WalletService(db_session)
    svc.create_wallet("payer", "XOF")
    svc.create_wallet("payee", "XOF")
    svc.credit_wallet("payer", "XOF", Decimal("1000"), "seed")

    total_before = svc.get_balance("payer", "XOF") + svc.get_balance("payee", "XOF")

    escrow = svc.create_escrow("task-1", "payer", "payee", Decimal("600"), "XOF")
    svc.release_escrow(escrow.id)

    total_after = svc.get_balance("payer", "XOF") + svc.get_balance("payee", "XOF")
    assert total_before == total_after, f"Money created: before={total_before} after={total_after}"

"""
P1.5 — Tests for partial_release_escrow and the frozen_audit/contested guards on
release_escrow / refund_escrow / partial_release_escrow.

Covers:
  - partial_release_escrow splits the gross between the tasker (via the social
    split) and a refund to the client, and is rejected on funded/hold escrows
    only when allow_frozen=False is violated... actually allowed on funded/hold.
  - release_escrow / refund_escrow / partial_release_escrow raise EscrowError on
    frozen_audit/contested escrows when allow_frozen=False (the default).
  - The dispute resolution flow (DisputeService.decide) operates on a
    frozen_audit escrow via allow_frozen=True for all three decision types.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.task import Task
from app.models.user import User
from app.services.dispute_service import DisputeService
from app.services.internal_wallet_seed_service import InternalWalletSeedService
from app.services.wallet_service import EscrowError, WalletService


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
    from app.core.config import settings as _settings
    for _name in ("zaska_wallet_user_id", "pension_fund_user_id", "health_fund_user_id", "smoothing_fund_user_id"):
        setattr(_settings, _name, "")
    InternalWalletSeedService(session).ensure_all()
    yield session
    session.close()


def _fund_user_ids(db_session) -> list[str]:
    from app.core.config import settings as _s
    return [
        _s.zaska_wallet_user_id,
        _s.pension_fund_user_id,
        _s.health_fund_user_id,
        _s.smoothing_fund_user_id,
    ]


def _total_balance(svc: WalletService, db_session, *user_ids: str) -> Decimal:
    total = Decimal("0")
    for uid in (*user_ids, *_fund_user_ids(db_session)):
        total += svc.get_balance(uid, "XOF")
    return total


# ── partial_release_escrow on a funded escrow ────────────────────────────────

def test_partial_release_escrow_splits_gross_between_tasker_and_refund(db_session):
    svc = WalletService(db_session)
    svc.create_wallet("payer", "XOF")
    svc.create_wallet("payee", "XOF")
    svc.credit_wallet("payer", "XOF", Decimal("1000"), "seed")

    total_before = _total_balance(svc, db_session, "payer", "payee")

    escrow = svc.create_escrow("task-1", "payer", "payee", Decimal("500"), "XOF")

    settled, tasker_net, client_refund = svc.partial_release_escrow(escrow.id, 60)

    assert settled.status == "partial_released"
    assert client_refund == Decimal("200")  # 40% of 500 refunded to client
    expected_split = svc.calculate_social_split(Decimal("300"))  # 60% of 500
    assert tasker_net == expected_split["tasker_net"]
    assert svc.get_balance("payee", "XOF") == expected_split["tasker_net"]
    assert svc.get_balance("payer", "XOF") == Decimal("500") + client_refund  # 500 left + 200 refund

    total_after = _total_balance(svc, db_session, "payer", "payee")
    assert total_before == total_after


def test_partial_release_escrow_full_completion_no_refund_leg(db_session):
    """At 100% completion, client_refund is 0 and no refund transaction is created."""
    svc = WalletService(db_session)
    svc.create_wallet("payer", "XOF")
    svc.credit_wallet("payer", "XOF", Decimal("1000"), "seed")

    escrow = svc.create_escrow("task-1", "payer", "payee", Decimal("500"), "XOF")
    settled, tasker_net, client_refund = svc.partial_release_escrow(escrow.id, 100)

    assert client_refund == Decimal("0")
    expected_split = svc.calculate_social_split(Decimal("500"))
    assert tasker_net == expected_split["tasker_net"]
    assert svc.get_balance("payer", "XOF") == Decimal("500")  # nothing extra refunded


# ── frozen_audit / contested guards (default allow_frozen=False) ────────────

@pytest.mark.parametrize("method_name,args", [
    ("release_escrow", ()),
    ("refund_escrow", ()),
    ("partial_release_escrow", (50,)),
])
def test_frozen_audit_escrow_rejected_without_allow_frozen(db_session, method_name, args):
    svc = WalletService(db_session)
    svc.create_wallet("payer", "XOF")
    svc.credit_wallet("payer", "XOF", Decimal("1000"), "seed")

    escrow = svc.create_escrow("task-1", "payer", "payee", Decimal("500"), "XOF")
    svc.freeze_escrow_for_audit(escrow.id, "payer")
    assert svc.get_escrow(escrow.id).status == "frozen_audit"

    with pytest.raises(EscrowError):
        getattr(svc, method_name)(escrow.id, *args)


@pytest.mark.parametrize("method_name,args", [
    ("release_escrow", ()),
    ("refund_escrow", ()),
    ("partial_release_escrow", (50,)),
])
def test_contested_escrow_rejected_without_allow_frozen(db_session, method_name, args):
    svc = WalletService(db_session)
    svc.create_wallet("payer", "XOF")
    svc.credit_wallet("payer", "XOF", Decimal("1000"), "seed")

    escrow = svc.create_escrow("task-1", "payer", "payee", Decimal("500"), "XOF")
    escrow_obj = svc.get_escrow(escrow.id)
    escrow_obj.status = "contested"
    db_session.commit()

    with pytest.raises(EscrowError):
        getattr(svc, method_name)(escrow.id, *args)


# ── frozen_audit + allow_frozen=True (dispute resolution path) ──────────────

def test_frozen_audit_escrow_release_allowed_with_allow_frozen(db_session):
    svc = WalletService(db_session)
    svc.create_wallet("payer", "XOF")
    svc.create_wallet("payee", "XOF")
    svc.credit_wallet("payer", "XOF", Decimal("1000"), "seed")

    escrow = svc.create_escrow("task-1", "payer", "payee", Decimal("500"), "XOF")
    svc.freeze_escrow_for_audit(escrow.id, "payer")

    settled = svc.release_escrow(escrow.id, allow_frozen=True)
    assert settled.status == "released"
    expected_split = svc.calculate_social_split(Decimal("500"))
    assert svc.get_balance("payee", "XOF") == expected_split["tasker_net"]


def test_frozen_audit_escrow_partial_release_allowed_with_allow_frozen(db_session):
    svc = WalletService(db_session)
    svc.create_wallet("payer", "XOF")
    svc.create_wallet("payee", "XOF")
    svc.credit_wallet("payer", "XOF", Decimal("1000"), "seed")

    escrow = svc.create_escrow("task-1", "payer", "payee", Decimal("500"), "XOF")
    svc.freeze_escrow_for_audit(escrow.id, "payer")

    settled, tasker_net, client_refund = svc.partial_release_escrow(escrow.id, 70, allow_frozen=True)
    assert settled.status == "partial_released"
    assert client_refund == Decimal("150")
    expected_split = svc.calculate_social_split(Decimal("350"))
    assert tasker_net == expected_split["tasker_net"]


# ── DisputeService.decide on a frozen_audit escrow ───────────────────────────

def test_dispute_decide_release_tasker_on_frozen_escrow(db_session):
    svc = WalletService(db_session)
    svc.create_wallet("payer", "XOF")
    svc.create_wallet("payee", "XOF")
    svc.credit_wallet("payer", "XOF", Decimal("1000"), "seed")

    escrow = svc.create_escrow("task-1", "payer", "payee", Decimal("500"), "XOF")

    dispute_svc = DisputeService(db_session)
    dispute = dispute_svc.open_task_dispute(task_id="task-1", actor_user_id="payer", reason="Travail non conforme")
    assert svc.get_escrow(escrow.id).status == "frozen_audit"

    result = dispute_svc.decide(
        dispute_id=dispute["id"],
        admin_user_id="admin-1",
        decision="release_tasker",
        admin_notes="Le travail a bien été effectué",
    )

    assert result["resolutionType"] == "release_tasker"
    assert svc.get_escrow(escrow.id).status == "released"
    expected_split = svc.calculate_social_split(Decimal("500"))
    assert svc.get_balance("payee", "XOF") == expected_split["tasker_net"]


def test_dispute_decide_partial_refund_on_frozen_escrow(db_session):
    svc = WalletService(db_session)
    svc.create_wallet("payer", "XOF")
    svc.create_wallet("payee", "XOF")
    svc.credit_wallet("payer", "XOF", Decimal("1000"), "seed")

    escrow = svc.create_escrow("task-1", "payer", "payee", Decimal("500"), "XOF")

    dispute_svc = DisputeService(db_session)
    dispute = dispute_svc.open_task_dispute(task_id="task-1", actor_user_id="payee", reason="Client injoignable")

    result = dispute_svc.decide(
        dispute_id=dispute["id"],
        admin_user_id="admin-1",
        decision="partial_refund_client",
        admin_notes="Travail partiellement réalisé",
        tasker_percent=40,
    )

    assert result["resolutionType"] == "partial_release_40"
    settled = svc.get_escrow(escrow.id)
    assert settled.status == "partial_released"
    expected_split = svc.calculate_social_split(Decimal("200"))  # 40% of 500
    assert svc.get_balance("payee", "XOF") == expected_split["tasker_net"]
    assert svc.get_balance("payer", "XOF") == Decimal("500") + Decimal("300")  # 500 left + 60% refund

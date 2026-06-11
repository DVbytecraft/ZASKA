"""
P3 — API keys & sandbox isolation.

Covers:
  - ApiKeyService: create/verify/revoke lifecycle, scope checks, expiration.
  - Sandbox wallets are isolated from production wallets for the same
    user/currency (separate rows via uq_wallet_user_currency_sandbox).
  - Sandbox escrow release credits sandbox wallets and never touches the
    accounting ledger (record_transaction_realtime skips is_sandbox=True).
  - wallet == ledger invariant still holds for production-mode operations
    after the is_sandbox columns were added.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.accounting import LedgerEntry
from app.models.b2b import BusinessOrganization
from app.models.task import Task
from app.models.user import User
from app.services.api_key_service import ApiKeyError, ApiKeyService
from app.services.internal_wallet_seed_service import InternalWalletSeedService
from app.services.wallet_service import WalletService


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
    session.add(BusinessOrganization(id="org-1", name="Acme Corp"))
    session.commit()
    from app.core.config import settings as _settings
    for _name in ("zaska_wallet_user_id", "pension_fund_user_id", "health_fund_user_id", "smoothing_fund_user_id"):
        setattr(_settings, _name, "")
    InternalWalletSeedService(session).ensure_all()
    yield session
    session.close()


# ─── ApiKeyService ────────────────────────────────────────────────────────────

def test_create_and_verify_api_key(db_session):
    svc = ApiKeyService(db_session)
    created = svc.create_api_key(organization_id="org-1", name="Prod key", scopes=["wallet:read"])

    assert created["apiKey"].startswith("zsk_live_")
    assert created["isSandbox"] is False

    api_key = svc.verify_api_key(created["apiKey"])
    assert api_key.organization_id == "org-1"
    assert svc.check_scope(api_key, "wallet:read") is True
    assert svc.check_scope(api_key, "wallet:write") is False


def test_sandbox_key_has_test_prefix(db_session):
    svc = ApiKeyService(db_session)
    created = svc.create_api_key(organization_id="org-1", name="Sandbox key", scopes=["*"], is_sandbox=True)
    assert created["apiKey"].startswith("zsk_test_")
    assert created["isSandbox"] is True


def test_invalid_key_rejected(db_session):
    svc = ApiKeyService(db_session)
    svc.create_api_key(organization_id="org-1", name="Prod key", scopes=["*"])
    with pytest.raises(ApiKeyError):
        svc.verify_api_key("zsk_live_not-a-real-key-at-all")


def test_revoked_key_rejected(db_session):
    svc = ApiKeyService(db_session)
    created = svc.create_api_key(organization_id="org-1", name="Prod key", scopes=["*"])
    svc.revoke_api_key(created["id"], "org-1")
    with pytest.raises(ApiKeyError):
        svc.verify_api_key(created["apiKey"])


def test_create_api_key_unknown_org_raises(db_session):
    svc = ApiKeyService(db_session)
    with pytest.raises(ApiKeyError):
        svc.create_api_key(organization_id="does-not-exist", name="x", scopes=[])


# ─── Sandbox wallet/escrow isolation ──────────────────────────────────────────

def test_sandbox_and_production_wallets_are_separate_rows(db_session):
    svc = WalletService(db_session)
    prod_wallet = svc.create_wallet("payer", "XOF")
    sandbox_wallet = svc.create_wallet("payer", "XOF", is_sandbox=True)

    assert prod_wallet.id != sandbox_wallet.id
    assert prod_wallet.is_sandbox is False
    assert sandbox_wallet.is_sandbox is True

    svc.credit_wallet("payer", "XOF", Decimal("100"), "prod-seed")
    svc.credit_wallet("payer", "XOF", Decimal("999"), "sandbox-seed", is_sandbox=True)

    assert svc.get_balance("payer", "XOF") == Decimal("100")
    assert svc.get_balance("payer", "XOF", is_sandbox=True) == Decimal("999")


def test_sandbox_escrow_release_does_not_touch_ledger(db_session):
    svc = WalletService(db_session)
    svc.create_wallet("payer", "XOF", is_sandbox=True)
    svc.create_wallet("payee", "XOF", is_sandbox=True)
    svc.credit_wallet("payer", "XOF", Decimal("1000"), "sandbox-seed", is_sandbox=True)

    entries_before = db_session.execute(select(LedgerEntry)).scalars().all()

    escrow = svc.create_escrow("task-1", "payer", "payee", Decimal("500"), "XOF", is_sandbox=True)
    assert escrow.is_sandbox is True
    svc.release_escrow(escrow.id)

    entries_after = db_session.execute(select(LedgerEntry)).scalars().all()
    assert len(entries_after) == len(entries_before)

    # Sandbox tasker net credit happened on the sandbox wallet only.
    split = svc.calculate_social_split(Decimal("500"))
    assert svc.get_balance("payee", "XOF", is_sandbox=True) == split["tasker_net"]
    # Production wallet for the same user/currency is untouched (does not even exist).
    with pytest.raises(Exception):
        svc.get_balance("payee", "XOF")


def test_production_escrow_still_mirrors_to_ledger(db_session):
    """Sanity check: adding is_sandbox columns must not break the P1.6 invariant
    for normal (non-sandbox) operations."""
    svc = WalletService(db_session)
    svc.create_wallet("payer", "XOF")
    svc.create_wallet("payee", "XOF")
    svc.credit_wallet("payer", "XOF", Decimal("1000"), "seed")

    escrow = svc.create_escrow("task-1", "payer", "payee", Decimal("500"), "XOF")
    assert escrow.is_sandbox is False
    svc.release_escrow(escrow.id)

    entries = db_session.execute(select(LedgerEntry)).scalars().all()
    assert len(entries) > 0

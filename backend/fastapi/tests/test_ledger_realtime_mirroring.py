"""
P1.6 — The accounting ledger must update automatically on every wallet
debit/credit, in real time, with no manual cron / admin endpoint trigger.

Covers:
  - release_escrow() immediately produces LedgerEntry rows for the social-split
    fund accounts (ZASKA_OPERATIONS, PENSION_FUND, HEALTH_FUND, SMOOTHING_FUND)
    and the TASKER_NET_DISTRIBUTION account, WITHOUT calling
    ingest_wallet_mirror_entries().
  - For each fund account, the ledger balance equals the fund wallet balance
    (wallet == ledger invariant), confirmed in real time.
  - Calling ingest_wallet_mirror_entries() afterwards creates zero additional
    entries (idempotent — realtime mirroring already covered everything).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.accounting import FinancialAccount, LedgerEntry
from app.models.task import Task
from app.models.user import User
from app.services.accounting_ledger_service import AccountingLedgerService
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
    session.commit()
    from app.core.config import settings as _settings
    for _name in ("zaska_wallet_user_id", "pension_fund_user_id", "health_fund_user_id", "smoothing_fund_user_id"):
        setattr(_settings, _name, "")
    InternalWalletSeedService(session).ensure_all()
    yield session
    session.close()


def _ledger_balance(db_session, code: str, currency: str) -> Decimal:
    account = db_session.execute(
        select(FinancialAccount).where(
            FinancialAccount.code == code,
            FinancialAccount.currency == currency,
        )
    ).scalars().one_or_none()
    if account is None:
        return Decimal("0")
    ledger_svc = AccountingLedgerService(db_session)
    return ledger_svc._ledger_balance_for_account(account.id)


def test_release_escrow_mirrors_to_ledger_in_realtime(db_session):
    svc = WalletService(db_session)
    svc.create_wallet("payer", "XOF")
    svc.create_wallet("payee", "XOF")
    svc.credit_wallet("payer", "XOF", Decimal("1000"), "seed")

    escrow = svc.create_escrow("task-1", "payer", "payee", Decimal("500"), "XOF")
    svc.release_escrow(escrow.id)

    from app.core.config import settings as _s

    fund_accounts = {
        "ZASKA_OPERATIONS": _s.zaska_wallet_user_id,
        "PENSION_FUND": _s.pension_fund_user_id,
        "HEALTH_FUND": _s.health_fund_user_id,
        "SMOOTHING_FUND": _s.smoothing_fund_user_id,
    }

    # Ledger entries already exist immediately after release_escrow() — no
    # manual ingest_wallet_mirror_entries() call was made.
    for code, user_id in fund_accounts.items():
        wallet_balance = svc.get_balance(user_id, "XOF")
        assert wallet_balance > Decimal("0")
        assert _ledger_balance(db_session, code, "XOF") == wallet_balance

    split = svc.calculate_social_split(Decimal("500"))
    assert _ledger_balance(db_session, "TASKER_NET_DISTRIBUTION", "XOF") == split["tasker_net"]


def test_ingest_after_realtime_mirroring_creates_no_duplicates(db_session):
    """ingest_wallet_mirror_entries() remains idempotent: since release_escrow()
    already mirrored every entry in real time, a manual ingest creates nothing new."""
    svc = WalletService(db_session)
    svc.create_wallet("payer", "XOF")
    svc.create_wallet("payee", "XOF")
    svc.credit_wallet("payer", "XOF", Decimal("1000"), "seed")

    escrow = svc.create_escrow("task-1", "payer", "payee", Decimal("500"), "XOF")
    svc.release_escrow(escrow.id)

    entries_before = db_session.execute(select(LedgerEntry)).scalars().all()

    ledger_svc = AccountingLedgerService(db_session)
    result = ledger_svc.ingest_wallet_mirror_entries()

    assert result["created_entries"] == 0

    entries_after = db_session.execute(select(LedgerEntry)).scalars().all()
    assert len(entries_after) == len(entries_before)


def test_credit_wallet_to_fund_user_mirrors_immediately(db_session):
    """A direct credit_wallet() to a fund-owned wallet is mirrored to its
    FinancialAccount in real time too (not only escrow-release credits)."""
    from app.core.config import settings as _s

    svc = WalletService(db_session)
    svc.credit_wallet(_s.pension_fund_user_id, "XOF", Decimal("250"), "manual-topup")

    assert _ledger_balance(db_session, "PENSION_FUND", "XOF") == Decimal("250")

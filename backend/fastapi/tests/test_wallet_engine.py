"""
Tests unitaires WalletService — aucune DB live requise (SQLite in-memory).

Couvre :
  - create_wallet (idempotence)
  - credit_wallet / debit_wallet (solde ACID)
  - InsufficientFundsError
  - create_escrow / release_escrow / refund_escrow
  - EscrowError sur double-action
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.user import User
from app.models.task import Task
from app.models.wallet import Escrow, Transaction, Wallet
from app.services.internal_wallet_seed_service import InternalWalletSeedService
from app.services.wallet_service import (
    EscrowError,
    InsufficientFundsError,
    WalletNotFoundError,
    WalletService,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def db_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    # SQLite ne supporte pas Numeric(20,6) directement — on force Float pour les tests
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session = Session()

    # Seed : un user et une task minimaux
    user_a = User(id="user-a", email="a@test.com", password_hash="x", role="client", is_verified=True)
    user_b = User(id="user-b", email="b@test.com", password_hash="x", role="worker", is_verified=True)
    task = Task(id="task-1", title="Test Task", description="Fixture task", price=1000.0, currency="XOF", latitude=6.13, longitude=1.22, status="OPEN", created_by="user-a")
    for obj in (user_a, user_b, task):
        if not session.get(type(obj), obj.id):
            session.add(obj)
    session.commit()

    # Social-split fund accounts (zaska_operations/pension/health/smoothing) must
    # be configured in this session's DB or release_escrow() hard-fails (P1.2).
    # Reset settings so InternalWalletSeedService re-binds them to users that
    # actually exist in THIS in-memory database (settings is a process-wide
    # singleton shared across test modules).
    from app.core.config import settings as _settings
    for _name in ("zaska_wallet_user_id", "pension_fund_user_id", "health_fund_user_id", "smoothing_fund_user_id"):
        setattr(_settings, _name, "")
    InternalWalletSeedService(session).ensure_all()

    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def svc(db_session) -> WalletService:
    return WalletService(db_session)


# ═══════════════════════════════════════════════════════════════════════════
# 1. create_wallet
# ═══════════════════════════════════════════════════════════════════════════

class TestCreateWallet:

    def test_creates_wallet_with_zero_balance(self, svc):
        wallet = svc.create_wallet("user-a", "EUR")
        assert wallet.balance == Decimal("0")
        assert wallet.currency == "EUR"

    def test_idempotent_second_call_returns_same(self, svc):
        w1 = svc.create_wallet("user-a", "EUR")
        w2 = svc.create_wallet("user-a", "EUR")
        assert w1.id == w2.id

    def test_different_currencies_create_distinct_wallets(self, svc):
        w_eur = svc.create_wallet("user-b", "EUR")
        w_xof = svc.create_wallet("user-b", "XOF")
        assert w_eur.id != w_xof.id
        assert w_eur.currency == "EUR"
        assert w_xof.currency == "XOF"


# ═══════════════════════════════════════════════════════════════════════════
# 2. credit_wallet
# ═══════════════════════════════════════════════════════════════════════════

class TestCreditWallet:

    def test_credit_increases_balance(self, svc):
        svc.create_wallet("user-a", "USD")
        svc.credit_wallet("user-a", "USD", Decimal("100"), "ref-credit-1")
        balance = svc.get_balance("user-a", "USD")
        assert balance == Decimal("100")

    def test_multiple_credits_accumulate(self, svc):
        svc.create_wallet("user-a", "GHS")
        svc.credit_wallet("user-a", "GHS", Decimal("50"), "ref-c1")
        svc.credit_wallet("user-a", "GHS", Decimal("75"), "ref-c2")
        assert svc.get_balance("user-a", "GHS") == Decimal("125")

    def test_credit_creates_transaction_record(self, svc):
        svc.create_wallet("user-a", "NGN")
        tx = svc.credit_wallet("user-a", "NGN", Decimal("200"), "ref-tx-check")
        assert tx.type == "credit"
        assert tx.amount == Decimal("200")
        assert tx.status == "completed"

    def test_credit_zero_raises_value_error(self, svc):
        svc.create_wallet("user-a", "XOF")
        with pytest.raises(ValueError):
            svc.credit_wallet("user-a", "XOF", Decimal("0"), "ref-zero")

    def test_credit_negative_raises_value_error(self, svc):
        svc.create_wallet("user-a", "XOF")
        with pytest.raises(ValueError):
            svc.credit_wallet("user-a", "XOF", Decimal("-10"), "ref-neg")

    def test_credit_auto_provisions_wallet(self, svc):
        # Pas de create_wallet préalable — doit auto-créer
        tx = svc.credit_wallet("user-b", "KES", Decimal("500"), "ref-autoprov")
        assert tx.type == "credit"
        assert svc.get_balance("user-b", "KES") == Decimal("500")


# ═══════════════════════════════════════════════════════════════════════════
# 3. debit_wallet
# ═══════════════════════════════════════════════════════════════════════════

class TestDebitWallet:

    def test_debit_decreases_balance(self, svc):
        svc.create_wallet("user-a", "ZAR")
        svc.credit_wallet("user-a", "ZAR", Decimal("300"), "fund-zar")
        svc.debit_wallet("user-a", "ZAR", Decimal("100"), "debit-zar")
        assert svc.get_balance("user-a", "ZAR") == Decimal("200")

    def test_debit_creates_transaction_record(self, svc):
        svc.create_wallet("user-b", "ZAR")
        svc.credit_wallet("user-b", "ZAR", Decimal("100"), "fund-b-zar")
        tx = svc.debit_wallet("user-b", "ZAR", Decimal("40"), "debit-b-zar")
        assert tx.type == "debit"
        assert tx.amount == Decimal("40")

    def test_debit_raises_if_insufficient_funds(self, svc):
        svc.create_wallet("user-a", "RWF")
        svc.credit_wallet("user-a", "RWF", Decimal("50"), "fund-rwf")
        with pytest.raises(InsufficientFundsError):
            svc.debit_wallet("user-a", "RWF", Decimal("100"), "over-debit")

    def test_debit_raises_wallet_not_found(self, svc):
        with pytest.raises(WalletNotFoundError):
            svc.debit_wallet("user-a", "TZS", Decimal("10"), "no-wallet")

    def test_balance_never_negative(self, svc):
        svc.create_wallet("user-b", "UGX")
        svc.credit_wallet("user-b", "UGX", Decimal("100"), "fund-ugx")
        with pytest.raises(InsufficientFundsError):
            svc.debit_wallet("user-b", "UGX", Decimal("101"), "over-ugx")
        assert svc.get_balance("user-b", "UGX") == Decimal("100")


# ═══════════════════════════════════════════════════════════════════════════
# 4. Escrow flow
# ═══════════════════════════════════════════════════════════════════════════

class TestEscrowFlow:

    def _fund_payer(self, svc: WalletService, amount: Decimal = Decimal("1000")) -> None:
        svc.credit_wallet("user-a", "XOF", amount, "fund-escrow-test")

    def test_create_escrow_debits_payer(self, svc):
        self._fund_payer(svc)
        balance_before = svc.get_balance("user-a", "XOF")
        svc.create_escrow("task-1", "user-a", "user-b", Decimal("200"), "XOF")
        balance_after = svc.get_balance("user-a", "XOF")
        assert balance_after == balance_before - Decimal("200")

    def test_create_escrow_status_is_funded(self, svc):
        self._fund_payer(svc)
        escrow = svc.create_escrow("task-1", "user-a", "user-b", Decimal("100"), "XOF")
        assert escrow.status == "funded"

    def test_release_escrow_credits_payee(self, svc):
        self._fund_payer(svc)
        svc.create_wallet("user-b", "XOF")
        balance_b_before = svc.get_balance("user-b", "XOF")
        escrow = svc.create_escrow("task-1", "user-a", "user-b", Decimal("300"), "XOF")
        svc.release_escrow(escrow.id)
        balance_b_after = svc.get_balance("user-b", "XOF")
        # social_v2 split — payee (tasker) receives tasker_net (77.5% of escrow amount)
        split = svc.calculate_social_split(Decimal("300"))
        assert balance_b_after == balance_b_before + split["tasker_net"]

    def test_release_escrow_status_becomes_released(self, svc):
        self._fund_payer(svc)
        escrow = svc.create_escrow("task-1", "user-a", "user-b", Decimal("50"), "XOF")
        released = svc.release_escrow(escrow.id)
        assert released.status == "released"

    def test_refund_escrow_credits_payer(self, svc):
        self._fund_payer(svc)
        balance_a_before = svc.get_balance("user-a", "XOF")
        escrow = svc.create_escrow("task-1", "user-a", "user-b", Decimal("400"), "XOF")
        svc.refund_escrow(escrow.id)
        balance_a_after = svc.get_balance("user-a", "XOF")
        assert balance_a_after == balance_a_before

    def test_refund_escrow_status_becomes_refunded(self, svc):
        self._fund_payer(svc)
        escrow = svc.create_escrow("task-1", "user-a", "user-b", Decimal("60"), "XOF")
        refunded = svc.refund_escrow(escrow.id)
        assert refunded.status == "refunded"

    def test_double_release_raises_escrow_error(self, svc):
        self._fund_payer(svc)
        escrow = svc.create_escrow("task-1", "user-a", "user-b", Decimal("70"), "XOF")
        svc.release_escrow(escrow.id)
        with pytest.raises(EscrowError):
            svc.release_escrow(escrow.id)

    def test_release_after_refund_raises_escrow_error(self, svc):
        self._fund_payer(svc)
        escrow = svc.create_escrow("task-1", "user-a", "user-b", Decimal("80"), "XOF")
        svc.refund_escrow(escrow.id)
        with pytest.raises(EscrowError):
            svc.release_escrow(escrow.id)

    def test_create_escrow_insufficient_funds_raises(self, svc):
        # Solde insuffisant pour l'escrow
        svc.create_wallet("user-a", "XOF")
        svc.credit_wallet("user-a", "XOF", Decimal("10"), "fund-low-balance")
        with pytest.raises(InsufficientFundsError):
            svc.create_escrow("task-1", "user-a", "user-b", Decimal("999999"), "XOF")

    def test_get_escrow_by_task_returns_escrow(self, svc):
        self._fund_payer(svc)
        created = svc.create_escrow("task-1", "user-a", "user-b", Decimal("90"), "XOF")
        found = svc.get_escrow_by_task("task-1")
        assert found is not None
        assert found.id == created.id

    def test_list_transactions_returns_wallet_history(self, svc):
        svc.create_wallet("user-a", "EUR")
        svc.credit_wallet("user-a", "EUR", Decimal("500"), "hist-1")
        svc.credit_wallet("user-a", "EUR", Decimal("200"), "hist-2")
        txs = svc.list_transactions("user-a", "EUR")
        assert len(txs) >= 2
        assert all(t.type == "credit" for t in txs if t.reference in ("hist-1", "hist-2"))


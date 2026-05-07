from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.task import Task
from app.models.user import User
from app.models.wallet import Transaction
from app.services.payment.webhook_queue import QueuedWebhookEvent, WebhookQueue
from app.services.wallet_service import WalletService


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = Session()
    db.add(User(id="u1", email="u1@test.com", password_hash="x", role="client", is_verified=True))
    db.add(User(id="u2", email="u2@test.com", password_hash="x", role="worker", is_verified=True))
    db.add(
        Task(
            id="t1",
            title="Test",
            description="desc",
            price=1000.0,
            currency="EUR",
            latitude=1.0,
            longitude=1.0,
            status="OPEN",
            created_by="u1",
        )
    )
    db.commit()
    try:
        yield db
    finally:
        db.close()


def test_stripe_test_card_flow_funds_escrow(db_session):
    svc = WalletService(db_session)
    esc = svc.create_pending_escrow("t1", "u1", "u2", Decimal("100"), "EUR")
    funded = svc.fund_escrow_from_payment(esc.id, "stripe", "pi_test_card_4242")
    assert funded.status == "funded"


def test_webhook_duplicate_idempotent(monkeypatch):
    class FakeRedis:
        def __init__(self):
            self.kv = {}
            self.lists = {}

        def rpush(self, key, value):
            self.lists.setdefault(key, []).append(value)

        def lpop(self, key):
            arr = self.lists.get(key, [])
            return arr.pop(0) if arr else None

        def setex(self, key, _ttl, value):
            self.kv[key] = value

        def get(self, key):
            return self.kv.get(key)

    fake = FakeRedis()
    monkeypatch.setattr("app.services.payment.webhook_queue.redis_sync", fake)

    item = QueuedWebhookEvent(
        provider="stripe",
        raw_body="{}",
        headers={},
        idempotency_key="stripe:evt_1",
        request_id="r1",
    )
    WebhookQueue.enqueue(item)
    got = WebhookQueue.pop()
    assert got is not None
    WebhookQueue.mark_processed("stripe:evt_1")
    assert WebhookQueue.is_processed("stripe:evt_1") is True


def test_release_escrow_credits_worker(db_session):
    svc = WalletService(db_session)
    esc = svc.create_pending_escrow("t1", "u1", "u2", Decimal("70"), "EUR")
    svc.fund_escrow_from_payment(esc.id, "stripe", "pi_release")
    svc.release_escrow_safe(esc.id)
    bal = svc.get_balance("u2", "EUR")
    assert bal == Decimal("70")


def test_double_webhook_funding_stays_idempotent(db_session):
    svc = WalletService(db_session)
    esc = svc.create_pending_escrow("t1", "u1", "u2", Decimal("80"), "EUR")
    svc.fund_escrow_from_payment(esc.id, "stripe", "pi_same")
    svc.fund_escrow_from_payment(esc.id, "stripe", "pi_same")
    txs = db_session.query(Transaction).filter(Transaction.reference == "pay:stripe:pi_same").all()
    assert len(txs) == 1

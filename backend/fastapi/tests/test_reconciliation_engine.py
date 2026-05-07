import json
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.wallet import Transaction
from app.services.payment.reconciliation_engine import ReconciliationEngine
from app.services.wallet_service import WalletService


def _db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)()


def test_reconcile_detects_paid_provider_not_db():
    db = _db()
    svc = WalletService(db)
    esc = svc.create_pending_escrow("t1", "u1", "u2", Decimal("100"), "XOF")

    w = svc._get_or_create_wallet("u1", "XOF")
    tx = Transaction(
        id="tx1",
        wallet_id=w.id,
        type="inbound",
        amount=Decimal("100"),
        status="completed",
        reference="pay:stripe:abc",
        provider="stripe",
        metadata_json=json.dumps({"escrow_id": esc.id, "task_id": "t1", "provider_tx_id": "abc"}),
    )
    db.add(tx)
    db.commit()

    report = ReconciliationEngine(db).reconcile_all("TG")
    assert any(m["type"] == "paid_in_provider_not_db" for m in report["mismatches"])


def test_reconcile_detects_duplicates():
    db = _db()
    svc = WalletService(db)
    esc = svc.create_pending_escrow("t2", "u1", "u2", Decimal("50"), "XOF")
    w = svc._get_or_create_wallet("u1", "XOF")
    for i in range(2):
        db.add(
            Transaction(
                id=f"tx{i}",
                wallet_id=w.id,
                type="inbound",
                amount=Decimal("50"),
                status="completed",
                reference=f"pay:stripe:dup{i}",
                provider="stripe",
                metadata_json=json.dumps({"escrow_id": esc.id, "task_id": "t2", "provider_tx_id": f"dup{i}"}),
            )
        )
    db.commit()

    report = ReconciliationEngine(db).reconcile_all("TG")
    assert any(m["type"] == "duplicate_payments" for m in report["mismatches"])

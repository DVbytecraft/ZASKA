from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.task import Task
from app.models.user import User
from app.services.wallet_service import EscrowError, WalletService


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    session.add(User(id="u1", email="u1@test.com", password_hash="x", role="client", is_verified=True))
    session.add(User(id="u2", email="u2@test.com", password_hash="x", role="worker", is_verified=True))
    session.add(
        Task(
            id="t1",
            title="Task",
            description="Task description",
            price=100.0,
            currency="XOF",
            latitude=6.0,
            longitude=1.0,
            status="OPEN",
            created_by="u1",
        )
    )
    session.commit()
    try:
        yield session
    finally:
        session.close()


def test_cannot_revert_success_to_pending_path(db_session):
    svc = WalletService(db_session)
    esc = svc.create_pending_escrow("t1", "u1", "u2", Decimal("100"), "XOF")
    svc.fund_escrow_from_payment(esc.id, "mock", "tx1")
    with pytest.raises(EscrowError):
        svc.cancel_pending_escrow(esc.id)


def test_funded_then_release_keeps_valid_lifecycle(db_session):
    svc = WalletService(db_session)
    esc = svc.create_pending_escrow("t1", "u1", "u2", Decimal("200"), "XOF")
    svc.fund_escrow_from_payment(esc.id, "mock", "tx2")
    released = svc.release_escrow(esc.id)
    assert released.status == "released"

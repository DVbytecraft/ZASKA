from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.task import Task
from app.models.user import User
from app.services.internal_wallet_seed_service import InternalWalletSeedService
from app.services.wallet_service import WalletService


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    session.add(User(id="user-a", email="a@test.com", password_hash="x", role="client", is_verified=True))
    session.add(User(id="user-b", email="b@test.com", password_hash="x", role="worker", is_verified=True))
    session.add(
        Task(
            id="task-safe-1",
            title="Task",
            description="Desc",
            price=200.0,
            currency="XOF",
            latitude=1.0,
            longitude=1.0,
            status="OPEN",
            created_by="user-a",
            assigned_to="user-b",
        )
    )
    session.commit()
    from app.core.config import settings as _settings
    for _name in ("zaska_wallet_user_id", "pension_fund_user_id", "health_fund_user_id", "smoothing_fund_user_id"):
        setattr(_settings, _name, "")
    InternalWalletSeedService(session).ensure_all()
    yield session
    session.close()


def test_safe_escrow_flow_finalize(db_session):
    svc = WalletService(db_session)
    svc.create_wallet("user-a", "XOF")
    svc.credit_wallet("user-a", "XOF", Decimal("1000"), "seed")

    escrow = svc.create_escrow("task-safe-1", "user-a", "user-b", Decimal("200"), "XOF")
    released = svc.release_escrow_safe(escrow.id)
    finalized = svc.finalize_transaction(released.id)

    assert released.status == "released"
    assert finalized.status == "released"

"""
Unit tests for KYC expiration logic.

No DB needed — exercises the model property and service approve() directly via SQLite.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.kyc import KYC_VALIDITY_DAYS, KycSubmission
from app.models.user import User
from app.services.kyc_service import KycService


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    session.add(User(id="admin-1", email="admin@test.com", password_hash="x", role="admin", is_verified=True))
    session.add(User(id="user-1", email="user@test.com", password_hash="x", role="client", is_verified=True))
    session.commit()
    session.add(
        KycSubmission(
            id="kyc-1",
            user_id="user-1",
            id_document_url="http://x/doc.jpg",
            selfie_url="http://x/selfie.jpg",
            status="pending",
        )
    )
    session.commit()
    yield session
    session.close()


def test_approve_sets_approved_at_and_expires_at(db_session):
    svc = KycService(db_session)
    before = datetime.now(timezone.utc)
    sub = svc.approve("kyc-1", reviewer_id="admin-1")
    after = datetime.now(timezone.utc)

    assert sub.status == "approved"
    assert sub.approved_at is not None
    assert before <= sub.approved_at <= after
    assert sub.expires_at is not None
    expected_expiry = sub.approved_at + timedelta(days=KYC_VALIDITY_DAYS)
    # Allow 1-second tolerance
    assert abs((sub.expires_at - expected_expiry).total_seconds()) < 1


def test_is_expired_false_for_fresh_approval(db_session):
    svc = KycService(db_session)
    sub = svc.approve("kyc-1", reviewer_id="admin-1")
    assert sub.is_expired is False


def test_is_expired_true_when_past_expires_at(db_session):
    sub = db_session.get(KycSubmission, "kyc-1")
    sub.status = "approved"
    sub.approved_at = datetime.now(timezone.utc) - timedelta(days=400)
    sub.expires_at = datetime.now(timezone.utc) - timedelta(days=35)
    db_session.commit()
    db_session.refresh(sub)

    assert sub.is_expired is True


def test_is_expired_false_when_expires_at_is_none(db_session):
    sub = db_session.get(KycSubmission, "kyc-1")
    sub.expires_at = None
    db_session.commit()
    db_session.refresh(sub)

    assert sub.is_expired is False

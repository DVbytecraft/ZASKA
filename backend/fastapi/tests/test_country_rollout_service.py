from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.location_config import Country
from app.services.country_rollout_service import CountryRolloutService


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    yield session
    session.close()


def test_priority_launch_country_is_created_active(db_session):
    service = CountryRolloutService(db_session)

    country = service.ensure_country("TG")

    assert country.iso_code == "TG"
    assert country.is_active is True
    assert country.signup_enabled is True
    assert country.launch_status == "ACTIVE"
    assert country.currency_code == "XOF"
    assert country.tax_rate == Decimal("18")


def test_legacy_priority_country_is_repaired_to_active(db_session):
    db_session.add(
        Country(
            name="Togo",
            city="Lome",
            iso_code="TG",
            is_active=False,
            signup_enabled=True,
            launch_status="PLANNED",
        )
    )
    db_session.commit()

    country = CountryRolloutService(db_session).ensure_country("TG")

    assert country.is_active is True
    assert country.signup_enabled is True
    assert country.launch_status == "ACTIVE"
    assert country.display_name_en
    assert country.display_name_fr
    assert country.currency_code == "XOF"
    assert country.payment_providers_json


def test_admin_disabled_priority_country_is_not_force_reactivated(db_session):
    db_session.add(
        Country(
            name="Togo",
            city="Lome",
            iso_code="TG",
            display_name_en="Togo",
            display_name_fr="Togo",
            currency_code="XOF",
            payment_providers_json='["fedapay"]',
            is_active=False,
            signup_enabled=False,
            launch_status="CONFIGURED",
        )
    )
    db_session.commit()

    country = CountryRolloutService(db_session).ensure_country("TG")

    assert country.is_active is False
    assert country.signup_enabled is False
    assert country.launch_status == "CONFIGURED"

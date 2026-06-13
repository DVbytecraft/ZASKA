"""Idempotent world-country seeding for Zaska rollout.

This script intentionally delegates to CountryRolloutService so it does not
reintroduce legacy countries with partial metadata or wrong rollout flags.
"""

from app.db.session import SessionLocal
from app.models.location_config import Currency
from app.services.country_rollout_service import CountryRolloutService


def run_seed():
    db = SessionLocal()
    try:
        CountryRolloutService(db).seed_catalog()
        if db.query(Currency).filter(Currency.code == "EUR").one_or_none() is None:
            db.add(Currency(code="EUR", name="Euro"))
        if db.query(Currency).filter(Currency.code == "XOF").one_or_none() is None:
            db.add(Currency(code="XOF", name="West African CFA franc"))
        if db.query(Currency).filter(Currency.code == "GHS").one_or_none() is None:
            db.add(Currency(code="GHS", name="Ghanaian Cedi"))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()

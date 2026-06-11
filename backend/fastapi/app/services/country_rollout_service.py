from __future__ import annotations

import json
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.country_engine.definitions import get_config
from app.core.world_country_catalog import get_country_reference, iter_country_references
from app.models.location_config import Country


_TAX_RATE_BY_COUNTRY: dict[str, Decimal] = {
    "TG": Decimal("18"),
    "BJ": Decimal("18"),
    "GH": Decimal("15"),
    "FR": Decimal("20"),
    "ES": Decimal("21"),
    "EE": Decimal("22"),
}

_AML_AUTHORITIES: dict[str, str] = {
    "FR": "TRACFIN",
    "EE": "FIU",
    "TG": "CENTIF",
}

_PRIORITY_ACTIVE_COUNTRIES = {"TG", "BJ", "GH", "NG", "CI", "SN", "EE", "FR", "ES"}

_KNOWN_CURRENCY_SYMBOLS: dict[str, str] = {
    "XOF": "FCFA",
    "XAF": "FCFA",
    "EUR": "EUR",
    "USD": "$",
    "GBP": "GBP",
    "CAD": "CAD",
    "GHS": "GHS",
    "NGN": "NGN",
}


class CountryRolloutService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def seed_catalog(self) -> None:
        for reference in iter_country_references():
            self.ensure_country(str(reference["iso_code"]))

    def get_by_code(self, country_code: str) -> Country | None:
        cc = country_code.strip().upper()
        return self.db.execute(
            select(Country).where((Country.iso_code == cc) | (Country.name == cc))
        ).scalars().first()

    def resolve_local_currency(self, country_code: str | None, fallback: str = "EUR") -> str:
        if not country_code:
            return fallback
        country = self.ensure_country(country_code)
        if country.currency_code:
            return country.currency_code
        return get_config(country_code).currency or fallback

    def ensure_country(self, country_code: str) -> Country:
        cc = country_code.strip().upper()
        existing = self.get_by_code(cc)
        reference = get_country_reference(cc) or {}
        display_en = str(reference.get("name_en") or cc)
        if existing is None:
            # Legacy rows from the old name+city seed have iso_code=NULL and a
            # display name (e.g. "Benin") instead of an ISO code. Match those
            # before inserting, otherwise we'd violate the unique name constraint.
            existing = self.db.execute(
                select(Country).where(Country.iso_code.is_(None), Country.name == display_en)
            ).scalars().first()
        if existing is not None:
            self._hydrate_missing_fields(existing, cc)
            self.db.commit()
            self.db.refresh(existing)
            return existing

        config = get_config(cc)
        provider_names = list(dict.fromkeys(config.payment_providers))
        display_fr = str(reference.get("name_fr") or display_en)
        primary_city_name = str(reference.get("primary_city_name") or cc)
        continent_code = str(reference.get("continent_code") or "OTHER")
        continent_name = str(reference.get("continent_name") or "Other")
        currency_code = str(reference.get("currency_code") or config.currency or "EUR")
        is_active = cc in _PRIORITY_ACTIVE_COUNTRIES

        country = Country(
            id=str(uuid.uuid4()),
            name=display_en,
            city=primary_city_name,
            iso_code=cc,
            display_name_en=display_en,
            display_name_fr=display_fr,
            phone_prefix=str(reference.get("phone_prefix") or "") or None,
            continent_code=continent_code,
            continent_name=continent_name,
            primary_city_name=primary_city_name,
            currency_code=currency_code,
            currency_symbol=str(reference.get("currency_symbol") or _KNOWN_CURRENCY_SYMBOLS.get(currency_code) or "") or None,
            timezone=str(reference.get("timezone") or config.timezone or "UTC"),
            payment_providers_json=json.dumps(provider_names),
            tax_rate=_TAX_RATE_BY_COUNTRY.get(cc, Decimal("0")),
            aml_reporting_threshold=Decimal("2000"),
            aml_authority_name=_AML_AUTHORITIES.get(cc),
            is_active=is_active,
            signup_enabled=is_active,
            launch_status="ACTIVE" if is_active else "PLANNED",
            mobile_money_enabled=config.mobile_money_enabled,
            stripe_enabled="stripe" in provider_names,
            fedapay_enabled="fedapay" in provider_names,
            flutterwave_enabled="flutterwave" in provider_names,
            paystack_enabled="paystack" in provider_names,
            food_delivery_enabled=False,
            food_delivery_escrow_minutes=20,
            restaurant_payment_split=True,
        )
        self.db.add(country)
        self.db.commit()
        self.db.refresh(country)
        return country

    def list_countries(self) -> list[Country]:
        self.seed_catalog()
        return self.db.execute(
            select(Country).order_by(
                Country.display_name_fr.asc(),
                Country.display_name_en.asc(),
                Country.name.asc(),
            )
        ).scalars().all()

    def list_signup_countries(self, query: str | None = None) -> list[Country]:
        self.seed_catalog()
        stmt = select(Country).where(
            Country.signup_enabled.is_(True),
            Country.is_active.is_(True),
        )
        if query:
            term = f"%{query.strip()}%"
            stmt = stmt.where(
                (Country.name.ilike(term))
                | (Country.display_name_en.ilike(term))
                | (Country.display_name_fr.ilike(term))
                | (Country.iso_code.ilike(term))
            )
        return self.db.execute(
            stmt.order_by(Country.display_name_fr.asc(), Country.display_name_en.asc(), Country.name.asc())
        ).scalars().all()

    def update_country(
        self,
        country_code: str,
        *,
        is_active: bool | None = None,
        signup_enabled: bool | None = None,
        launch_status: str | None = None,
        food_delivery_enabled: bool | None = None,
        food_delivery_escrow_minutes: int | None = None,
    ) -> Country:
        country = self.ensure_country(country_code)
        if is_active is not None:
            country.is_active = is_active
        if signup_enabled is not None:
            country.signup_enabled = signup_enabled
        if launch_status is not None:
            country.launch_status = launch_status
        if food_delivery_enabled is not None:
            country.food_delivery_enabled = food_delivery_enabled
        if food_delivery_escrow_minutes is not None:
            country.food_delivery_escrow_minutes = food_delivery_escrow_minutes
        self.db.commit()
        self.db.refresh(country)
        return country

    def assert_country_signup_open(self, country_code: str) -> Country:
        country = self.ensure_country(country_code)
        if not country.signup_enabled or not country.is_active:
            label = country.display_name_fr or country.display_name_en or country.name or country_code
            raise ValueError(
                f"{label} n'est pas encore couvert par Zaska. "
                "Vous ne pouvez pas encore vous inscrire avec ce pays."
            )
        return country

    def assert_country_live(self, country_code: str) -> Country:
        country = self.ensure_country(country_code)
        if not country.signup_enabled or not country.is_active:
            raise ValueError(
                "Votre pays n'est pas encore couvert par Zaska. "
                "Les operations ne sont pas encore disponibles dans cette zone."
            )
        return country

    def _hydrate_missing_fields(self, country: Country, country_code: str) -> None:
        reference = get_country_reference(country_code) or {}
        config = get_config(country_code)
        provider_names = list(dict.fromkeys(config.payment_providers))
        display_en = str(reference.get("name_en") or country.name or country_code)
        display_fr = str(reference.get("name_fr") or display_en)
        currency_code = str(reference.get("currency_code") or config.currency or country.currency_code or "EUR")
        country.iso_code = country.iso_code or country_code
        country.display_name_en = country.display_name_en or display_en
        country.display_name_fr = country.display_name_fr or display_fr
        country.phone_prefix = country.phone_prefix or (str(reference.get("phone_prefix") or "") or None)
        country.continent_code = country.continent_code or (str(reference.get("continent_code") or "") or None)
        country.continent_name = country.continent_name or (str(reference.get("continent_name") or "") or None)
        country.primary_city_name = country.primary_city_name or (str(reference.get("primary_city_name") or "") or None)
        country.city = country.city or country.primary_city_name or country.name
        country.currency_code = country.currency_code or currency_code
        country.currency_symbol = country.currency_symbol or (
            str(reference.get("currency_symbol") or _KNOWN_CURRENCY_SYMBOLS.get(currency_code) or "") or None
        )
        country.timezone = country.timezone or str(reference.get("timezone") or config.timezone or "UTC")
        country.payment_providers_json = country.payment_providers_json or json.dumps(provider_names)
        if country.tax_rate is None:
            country.tax_rate = _TAX_RATE_BY_COUNTRY.get(country_code, Decimal("0"))
        if country.aml_reporting_threshold is None:
            country.aml_reporting_threshold = Decimal("2000")
        country.aml_authority_name = country.aml_authority_name or _AML_AUTHORITIES.get(country_code)

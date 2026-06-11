import uuid

from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Country(Base):
    __tablename__ = "countries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(120), unique=True)
    city: Mapped[str] = mapped_column(String(120))
    iso_code: Mapped[str | None] = mapped_column(String(2), unique=True, index=True, nullable=True)
    display_name_en: Mapped[str | None] = mapped_column(String(120), nullable=True)
    display_name_fr: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone_prefix: Mapped[str | None] = mapped_column(String(16), nullable=True)
    continent_code: Mapped[str | None] = mapped_column(String(8), nullable=True, index=True)
    continent_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    primary_city_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    currency_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    currency_symbol: Mapped[str | None] = mapped_column(String(8), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payment_providers_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    pricing_profile_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0"), nullable=False, server_default="0")
    aml_reporting_threshold: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=Decimal("0"), nullable=False, server_default="0")
    aml_authority_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    signup_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="true")
    launch_status: Mapped[str] = mapped_column(String(16), default="PLANNED", nullable=False, server_default="PLANNED")
    mobile_money_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    stripe_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    fedapay_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    flutterwave_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    paystack_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    food_delivery_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    food_delivery_escrow_minutes: Mapped[int] = mapped_column(Integer, default=20, nullable=False, server_default="20")
    restaurant_payment_split: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="true")


class Currency(Base):
    __tablename__ = "currencies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(8), unique=True)
    name: Mapped[str] = mapped_column(String(120))


class PaymentMethodConfig(Base):
    __tablename__ = "payment_methods_config"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    country_id: Mapped[str] = mapped_column(String(36), ForeignKey("countries.id"))
    method_name: Mapped[str] = mapped_column(String(100))


class EmergencyNumber(Base):
    __tablename__ = "emergency_numbers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    country_id: Mapped[str] = mapped_column(String(36), ForeignKey("countries.id"))
    service_name: Mapped[str] = mapped_column(String(100))
    phone_number: Mapped[str] = mapped_column(String(32))

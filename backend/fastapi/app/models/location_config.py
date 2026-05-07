import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Country(Base):
    __tablename__ = "countries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(120), unique=True)
    city: Mapped[str] = mapped_column(String(120))


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

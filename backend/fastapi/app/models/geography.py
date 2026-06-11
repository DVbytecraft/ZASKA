from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Continent(Base):
    __tablename__ = "continents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(8), unique=True, nullable=False, index=True)
    name_en: Mapped[str] = mapped_column(String(128), nullable=False)
    name_fr: Mapped[str] = mapped_column(String(128), nullable=False)
    pricing_profile_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    launch_status: Mapped[str] = mapped_column(String(16), nullable=False, default="CONFIGURED", server_default="CONFIGURED")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class City(Base):
    __tablename__ = "cities"
    __table_args__ = (UniqueConstraint("country_id", "slug", name="uq_city_country_slug"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    country_id: Mapped[str] = mapped_column(String(36), ForeignKey("countries.id"), nullable=False, index=True)
    continent_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    launch_status: Mapped[str] = mapped_column(String(16), nullable=False, default="CONFIGURED", server_default="CONFIGURED")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ServiceZone(Base):
    __tablename__ = "service_zones"
    __table_args__ = (UniqueConstraint("city_id", "module_code", "slug", name="uq_service_zone_city_module_slug"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    country_id: Mapped[str] = mapped_column(String(36), ForeignKey("countries.id"), nullable=False, index=True)
    city_id: Mapped[str] = mapped_column(String(36), ForeignKey("cities.id"), nullable=False, index=True)
    continent_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    module_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    zone_type: Mapped[str] = mapped_column(String(32), nullable=False, default="radius", server_default="radius")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    launch_status: Mapped[str] = mapped_column(String(16), nullable=False, default="CONFIGURED", server_default="CONFIGURED")
    center_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    center_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    radius_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    coverage_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    pricing_profile_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

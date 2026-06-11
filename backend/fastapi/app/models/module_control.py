from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class PlatformModule(Base):
    __tablename__ = "platform_modules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    module_group: Mapped[str] = mapped_column(String(64), nullable=False, default="core", server_default="core")
    default_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    requires_country_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
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


class ModuleActivationSetting(Base):
    __tablename__ = "module_activation_settings"
    __table_args__ = (
        UniqueConstraint("module_id", "scope_type", "scope_value", name="uq_module_scope"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    module_id: Mapped[str] = mapped_column(String(36), ForeignKey("platform_modules.id"), nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    scope_value: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    updated_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
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


class ModuleActivationAudit(Base):
    __tablename__ = "module_activation_audit"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    module_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    scope_value: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    previous_enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    new_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    previous_config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

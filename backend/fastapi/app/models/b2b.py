import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BusinessOrganization(Base):
    __tablename__ = "business_organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(160), index=True)
    legal_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    registration_number: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    continent_code: Mapped[str | None] = mapped_column(String(8), nullable=True, index=True)
    billing_mode: Mapped[str] = mapped_column(String(24), default="monthly_invoice", nullable=False, server_default="monthly_invoice")
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False, server_default="active", index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class BusinessMembership(Base):
    __tablename__ = "business_memberships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("business_organizations.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    member_role: Mapped[str] = mapped_column(String(32), default="manager", nullable=False, server_default="manager")
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False, server_default="active")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class BusinessContract(Base):
    __tablename__ = "business_contracts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("business_organizations.id"), index=True)
    plan_name: Mapped[str] = mapped_column(String(64))
    monthly_task_quota: Mapped[int | None] = mapped_column(nullable=True)
    overage_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="EUR", nullable=False, server_default="EUR")
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False, server_default="active", index=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    terms_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class BusinessTaskTemplate(Base):
    __tablename__ = "business_task_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("business_organizations.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    service_category: Mapped[str] = mapped_column(String(32), default="TASK", nullable=False, server_default="TASK")
    default_price: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    currency: Mapped[str] = mapped_column(String(8), default="EUR", nullable=False, server_default="EUR")
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="true")
    template_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class BusinessWorkOrder(Base):
    __tablename__ = "business_work_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("business_organizations.id"), index=True)
    template_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("business_task_templates.id"), nullable=True, index=True)
    requested_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    assigned_tasker_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    linked_task_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=True, index=True)
    beneficiary_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    beneficiary_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="draft", nullable=False, server_default="draft", index=True)
    source: Mapped[str] = mapped_column(String(24), default="b2b", nullable=False, server_default="b2b")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    currency: Mapped[str] = mapped_column(String(8), default="EUR", nullable=False, server_default="EUR")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ApiKey(Base):
    """API key issued to a BusinessOrganization for programmatic access.

    The raw key is shown to the caller exactly once at creation time; only its
    bcrypt hash is persisted. `key_prefix` (first chars of the raw key) is
    stored in clear so the right row can be looked up cheaply before hashing
    the full candidate key for comparison.
    """

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("business_organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    key_prefix: Mapped[str] = mapped_column(String(16), index=True, unique=True)
    key_hash: Mapped[str] = mapped_column(String(255))
    # JSON list of scope strings, e.g. ["wallet:read", "tasks:write"]
    scopes_json: Mapped[str] = mapped_column(Text, default="[]", server_default="[]")
    # Sandbox keys only ever touch is_sandbox=True wallets/transactions/escrows.
    is_sandbox: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    rate_limit_per_minute: Mapped[int] = mapped_column(default=60, server_default="60")
    # active | revoked
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False, server_default="active", index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AdminExportJob(Base):
    __tablename__ = "admin_export_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_type: Mapped[str] = mapped_column(String(64), index=True)
    export_format: Mapped[str] = mapped_column(String(16), default="csv", nullable=False, server_default="csv")
    status: Mapped[str] = mapped_column(String(24), default="completed", nullable=False, server_default="completed", index=True)
    requested_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    continent_code: Mapped[str | None] = mapped_column(String(8), nullable=True, index=True)
    filters_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

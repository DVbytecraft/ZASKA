import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    phone: Mapped[str | None] = mapped_column(String(32), unique=True, index=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    referral_code: Mapped[str | None] = mapped_column(String(32), unique=True, index=True, nullable=True)
    referred_by_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    first_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(16), default="client")
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ban_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    suspension_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    tasker_security_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    biometric_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    criminal_record_status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False, server_default="pending")
    fcm_token: Mapped[str | None] = mapped_column(String(512), nullable=True)
    rating_sum: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, server_default="0")
    rating_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")
    client_rating_sum: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, server_default="0")
    client_rating_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")
    premium_access_restricted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    premium_access_restricted_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    premium_access_restricted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    aml_status: Mapped[str] = mapped_column(String(24), default="clear", nullable=False, server_default="clear")
    aml_review_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    aml_review_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    aml_last_case_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    # Enriched profile fields (migration 0039)
    bio: Mapped[str | None] = mapped_column(String(512), nullable=True)
    city: Mapped[str | None] = mapped_column(String(64), nullable=True)
    availability: Mapped[str | None] = mapped_column(String(32), nullable=True)
    hourly_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    response_time: Mapped[str | None] = mapped_column(String(32), nullable=True)
    welcome_email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

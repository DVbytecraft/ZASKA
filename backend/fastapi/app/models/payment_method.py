import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PaymentMethod(Base):
    __tablename__ = "payment_methods"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", "phone_number", name="uq_payment_method_user_provider_phone"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    method_type: Mapped[str] = mapped_column(String(64))          # mobile_money | card | bank
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)   # tmoney, flooz, orange_money, wave, mtn_momo, mpesa...
    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(4), nullable=True)
    nickname: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[str] = mapped_column(String(255))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

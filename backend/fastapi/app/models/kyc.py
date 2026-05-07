import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# KYC approval validity: 1 year (365 days). After this the user must resubmit.
KYC_VALIDITY_DAYS = 365


class KycSubmission(Base):
    __tablename__ = "kyc_submissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    id_document_url: Mapped[str] = mapped_column(String(500))
    selfie_url: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    reviewed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

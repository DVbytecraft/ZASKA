import uuid
from datetime import datetime, timezone
import json

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# KYC approval validity: 1 year (365 days). After this the user must resubmit.
KYC_VALIDITY_DAYS = 365


class KycSubmission(Base):
    __tablename__ = "kyc_submissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    id_document_url: Mapped[str] = mapped_column(String(500))
    id_document_back_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    selfie_url: Mapped[str] = mapped_column(String(500))
    submission_kind: Mapped[str] = mapped_column(String(16), default="full")
    id_document_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    id_document_number_masked: Mapped[str | None] = mapped_column(String(64), nullable=True)
    document_country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    biometric_selfie_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    biometric_status: Mapped[str] = mapped_column(String(24), default="pending")
    face_match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    liveness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ocr_status: Mapped[str] = mapped_column(String(24), default="pending")
    ocr_payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    criminal_record_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    criminal_record_status: Mapped[str] = mapped_column(String(24), default="pending")
    criminal_record_issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    criminal_record_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    criminal_record_risk_level: Mapped[str] = mapped_column(String(24), default="pending")
    criminal_record_analysis_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    renewal_of_submission_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    reviewed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    @staticmethod
    def _as_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @property
    def is_expired(self) -> bool:
        expires_at = self._as_utc(self.expires_at)
        if expires_at is None:
            return False
        return datetime.now(timezone.utc) > expires_at

    @property
    def metadata_payload(self) -> dict | None:
        if not self.metadata_json:
            return None
        try:
            return json.loads(self.metadata_json)
        except Exception:
            return None

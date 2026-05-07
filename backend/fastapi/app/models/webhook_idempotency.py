import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class WebhookIdempotency(Base):
    """Persistent webhook deduplication record.

    Redis alone is insufficient because TTL expiry can cause duplicate processing
    on provider retries that arrive after the Redis key expires.
    This table provides a durable, append-only record of processed webhook events.
    """

    __tablename__ = "webhook_idempotency"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    payload_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.core.redis_client import redis_sync

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass(frozen=True)
class QueuedWebhookEvent:
    provider: str
    raw_body: str
    headers: dict[str, str]
    idempotency_key: str
    request_id: str
    retry_count: int = 0


class WebhookQueue:
    QUEUE_KEY = "payment:webhooks:queue"
    DLQ_KEY = "payment:webhooks:dlq"
    PROCESSED_PREFIX = "payment:webhooks:processed:"
    RETRY_MAX = 5

    @classmethod
    def enqueue(cls, event: QueuedWebhookEvent) -> None:
        redis_sync.rpush(cls.QUEUE_KEY, json.dumps(event.__dict__))

    @classmethod
    def pop(cls) -> dict | None:
        raw = redis_sync.lpop(cls.QUEUE_KEY)
        return json.loads(raw) if raw else None

    @classmethod
    def mark_processed(
        cls,
        idempotency_key: str,
        *,
        db: "Session | None" = None,
        provider: str = "",
        event_type: str = "",
    ) -> None:
        """Mark a webhook as processed in Redis (fast) and optionally in DB (durable)."""
        redis_sync.setex(f"{cls.PROCESSED_PREFIX}{idempotency_key}", 86400 * 7, "1")
        if db is not None:
            cls._persist_to_db(db, idempotency_key, provider=provider, event_type=event_type)

    @classmethod
    def is_processed(cls, idempotency_key: str, *, db: "Session | None" = None) -> bool:
        """Check Redis first (fast path), then DB as durable fallback."""
        if redis_sync.get(f"{cls.PROCESSED_PREFIX}{idempotency_key}"):
            return True
        if db is not None:
            return cls._check_db(db, idempotency_key)
        return False

    @classmethod
    def _persist_to_db(
        cls,
        db: "Session",
        idempotency_key: str,
        *,
        provider: str,
        event_type: str,
    ) -> None:
        from app.models.webhook_idempotency import WebhookIdempotency

        try:
            existing = db.execute(
                select(WebhookIdempotency).where(
                    WebhookIdempotency.idempotency_key == idempotency_key
                )
            ).scalars().one_or_none()
            if existing is None:
                record = WebhookIdempotency(
                    idempotency_key=idempotency_key,
                    provider=provider,
                    event_type=event_type,
                )
                db.add(record)
                db.commit()
        except Exception:
            db.rollback()

    @classmethod
    def _check_db(cls, db: "Session", idempotency_key: str) -> bool:
        from app.models.webhook_idempotency import WebhookIdempotency

        try:
            record = db.execute(
                select(WebhookIdempotency).where(
                    WebhookIdempotency.idempotency_key == idempotency_key
                )
            ).scalars().one_or_none()
            if record is not None:
                redis_sync.setex(
                    f"{cls.PROCESSED_PREFIX}{idempotency_key}", 86400 * 7, "1"
                )
                return True
        except Exception:
            pass
        return False

    @classmethod
    def requeue_or_dlq(cls, payload: dict) -> None:
        retries = int(payload.get("retry_count", 0)) + 1
        payload["retry_count"] = retries
        if retries > cls.RETRY_MAX:
            redis_sync.rpush(cls.DLQ_KEY, json.dumps(payload))
            return
        redis_sync.rpush(cls.QUEUE_KEY, json.dumps(payload))

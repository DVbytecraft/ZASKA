"""Transactional Outbox Service.

Provides helpers to:
1. Write outbox events in the same DB transaction as the business mutation.
2. Process pending events with retry / dead-letter logic.

Usage in a service or router:
    from app.services.outbox_service import OutboxService
    svc = OutboxService(db)
    svc.enqueue(
        event_type="escrow.released",
        aggregate_id=escrow.id,
        aggregate_type="escrow",
        payload={"escrow_id": escrow.id, "task_id": escrow.task_id, ...},
        idempotency_key=f"escrow_release:{escrow.id}",
    )
    db.commit()   # ← business state + outbox event committed atomically

The scheduler (or Celery) calls OutboxService.process_pending() to deliver.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.outbox_event import OutboxEvent

logger = logging.getLogger(__name__)

# Exponential backoff delays per retry attempt (seconds)
_BACKOFF = [30, 120, 300, 900, 3600]


def _uuid() -> str:
    return str(uuid.uuid4())


class OutboxService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def enqueue(
        self,
        event_type: str,
        aggregate_id: str,
        aggregate_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
        max_retries: int = 5,
    ) -> OutboxEvent:
        """Write an outbox event.  Call inside the same transaction as the business write.

        If an event with the same idempotency_key already exists (duplicate request),
        the existing event is returned without creating a duplicate.
        """
        existing = self.db.execute(
            select(OutboxEvent).where(OutboxEvent.idempotency_key == idempotency_key)
        ).scalars().one_or_none()
        if existing is not None:
            return existing

        event = OutboxEvent(
            id=_uuid(),
            event_type=event_type,
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            payload=json.dumps(payload),
            idempotency_key=idempotency_key,
            status="pending",
            max_retries=max_retries,
        )
        self.db.add(event)
        return event

    @classmethod
    def process_pending(cls, db: Session, batch_size: int = 50) -> dict[str, int]:
        """Process up to batch_size pending outbox events.

        P0-004 FIX: After db.rollback(), SQLAlchemy expires all ORM objects.
        We re-read the event by ID after rollback to avoid DetachedInstanceError
        or stale reads on event.retry_count.

        Returns {"delivered": N, "failed": N, "dead_letter": N}.
        """
        now = datetime.utcnow()
        # Collect only IDs first — avoid holding stale ORM references across rollbacks
        pending_ids: list[str] = db.execute(
            select(OutboxEvent.id)
            .where(
                OutboxEvent.status.in_(["pending", "processing"]),
                (OutboxEvent.next_attempt_at == None) | (OutboxEvent.next_attempt_at <= now),  # noqa: E711
            )
            .order_by(OutboxEvent.created_at)
            .limit(batch_size)
        ).scalars().all()

        delivered = failed = dead = 0

        for event_id in pending_ids:
            try:
                # Lock the specific event row for this processing attempt
                event = db.execute(
                    select(OutboxEvent)
                    .where(OutboxEvent.id == event_id)
                    .with_for_update(skip_locked=True)
                ).scalars().one_or_none()

                if event is None:
                    continue  # Another worker picked it up — skip

                if event.status not in ("pending", "processing"):
                    continue  # State changed since we read IDs — skip

                event.status = "processing"
                db.flush()

                # Capture fields needed for retry logic before any rollback
                event_type = event.event_type
                event_aggregate_id = event.aggregate_id
                event_payload_raw = event.payload
                event_max_retries = event.max_retries

                _deliver_payload(event_type, event_aggregate_id, event_payload_raw)

                event.status = "delivered"
                event.delivered_at = datetime.utcnow()
                db.commit()
                delivered += 1

            except Exception as exc:
                # P0-004: rollback expires all ORM objects — re-read by ID
                db.rollback()
                try:
                    # Fresh read after rollback — event object from before is expired
                    fresh_event = db.execute(
                        select(OutboxEvent)
                        .where(OutboxEvent.id == event_id)
                        .with_for_update()
                    ).scalars().one_or_none()

                    if fresh_event is None:
                        continue  # Deleted between retries — skip

                    fresh_event.retry_count += 1
                    fresh_event.error = str(exc)[:500]

                    if fresh_event.retry_count >= fresh_event.max_retries:
                        fresh_event.status = "dead_letter"
                        dead += 1
                        logger.error(
                            "outbox: dead_letter event_type=%s id=%s after %s retries: %s",
                            fresh_event.event_type, event_id, fresh_event.retry_count, exc,
                        )
                    else:
                        delay = _BACKOFF[min(fresh_event.retry_count - 1, len(_BACKOFF) - 1)]
                        fresh_event.status = "pending"
                        fresh_event.next_attempt_at = datetime.utcnow() + timedelta(seconds=delay)
                        failed += 1
                        logger.warning(
                            "outbox: retry event_type=%s id=%s attempt=%s next_in=%ss: %s",
                            fresh_event.event_type, event_id, fresh_event.retry_count, delay, exc,
                        )
                    db.commit()
                except Exception as inner_exc:
                    logger.error("outbox: failed to update retry state for event=%s: %s", event_id, inner_exc)
                    db.rollback()

        return {"delivered": delivered, "failed": failed, "dead_letter": dead}


def _deliver_payload(event_type: str, aggregate_id: str, payload_raw: str) -> None:
    """Dispatch an outbox event to its side-effect handler.

    P0-001 FIX: The processor runs in a thread (run_in_executor).  WebSocket
    connections are bound to the main asyncio event loop and CANNOT be accessed
    from a different thread or event loop.  Instead of calling ws.send_text()
    directly, we publish to Redis — the Redis subscriber on each instance picks
    it up and delivers to local WS connections via the correct event loop.
    """
    payload = json.loads(payload_raw)

    if event_type.startswith("chat."):
        _deliver_chat_via_redis(aggregate_id, payload)
    elif event_type.startswith("call."):
        _deliver_call_via_redis(aggregate_id, payload)
    elif event_type.startswith("notification."):
        _deliver_notification(aggregate_id, payload)
    elif event_type.startswith("escrow."):
        logger.info("outbox: escrow event logged event_type=%s aggregate_id=%s", event_type, aggregate_id)
    else:
        logger.info("outbox: no handler for event_type=%s — marking delivered", event_type)


def _deliver_chat_via_redis(task_id: str, payload: dict) -> None:
    """Publish chat message to Redis — the WS subscriber delivers to local connections.

    P0-001: Never access chat_ws_manager.connections from a thread; use Redis pub/sub.
    """
    from app.core.redis_client import redis_sync
    channel = f"task-chat:{task_id}"
    try:
        redis_sync.publish(channel, json.dumps(payload))
    except Exception as exc:
        logger.warning("outbox: Redis publish failed for chat task=%s — %s", task_id, exc)
        raise  # Re-raise so the outbox processor can retry


def _deliver_call_via_redis(user_id: str, payload: dict) -> None:
    """Publish call notification to Redis for cross-instance delivery.

    P0-001: Same pattern as chat — Redis pub/sub bridges to the WS subscriber.
    """
    from app.core.redis_client import redis_sync
    channel = f"user:call_notify:{user_id}"
    try:
        redis_sync.publish(channel, json.dumps(payload))
    except Exception as exc:
        logger.warning("outbox: Redis publish failed for call user=%s — %s", user_id, exc)
        raise


def _deliver_notification(user_id: str, payload: dict) -> None:
    """Deliver a push notification via FCM.

    AUDIT-03 FIX — Silent failure not retried:
      OLD: try/except swallowed PushService errors → outbox marked event "delivered"
           even when the FCM call failed → notifications silently dropped forever,
           never retried, never dead-lettered, never alerted on.
      NEW: Let the exception propagate to process_pending() which handles retry/dead-letter.
           Transient FCM errors (network blip, rate-limit) are retried with exponential
           backoff; persistent failures go to dead_letter for manual inspection.
    """
    from app.services.push_service import PushService
    uid = payload.get("user_id", user_id)
    title = payload.get("title", "ZASKA")
    body = payload.get("body", "")
    if uid:
        PushService.send(user_id=uid, title=title, body=body)  # exception → retry in outbox

"""System Event Ledger — append-only immutable audit trail (Layer 2).

Usage:
    from app.services.event_ledger import EventLedger

    # Inside any router or service (within an open DB session):
    EventLedger.log(
        db=db,
        event_type="escrow.released",
        actor_id=user_id,
        aggregate_id=escrow.id,
        aggregate_type="escrow",
        payload={
            "amount": str(escrow.amount),
            "currency": escrow.currency,
            "task_id": escrow.task_id,
        },
        correlation_id=escrow.id,
        request_id=request_id,
    )

    # Do NOT commit here — EventLedger.log() flushes the event to the current
    # transaction.  The caller's db.commit() will persist both the business
    # mutation and the audit event atomically.

Rules:
    - NEVER call db.commit() inside EventLedger.log() — always co-commit with the
      business mutation to ensure atomicity.
    - NEVER call EventLedger.log() outside a transaction.
    - Failures to write the ledger must NEVER block the business operation.
      Call with best_effort=True (default) to silently continue on failure.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class EventLedger:
    @staticmethod
    def log(
        db: Session,
        event_type: str,
        aggregate_id: str,
        aggregate_type: str,
        payload: dict[str, Any],
        actor_id: str | None = None,
        actor_type: str = "user",
        correlation_id: str | None = None,
        request_id: str | None = None,
        ip_address: str | None = None,
        best_effort: bool = True,
    ) -> None:
        """Append an immutable event to the system_events ledger.

        Must be called WITHIN an active DB transaction.  Flushes (not commits)
        so the event is part of the enclosing transaction.

        Args:
            best_effort: If True (default), swallow any exception so the caller
                         is never blocked by ledger write failure.
        """
        try:
            from sqlalchemy import text

            event_id = str(uuid.uuid4())
            db.execute(
                text(
                    """
                    INSERT INTO system_events
                        (id, event_type, actor_id, actor_type, aggregate_id, aggregate_type,
                         payload, request_id, correlation_id, ip_address, created_at)
                    VALUES
                        (:id, :event_type, :actor_id, :actor_type, :aggregate_id, :aggregate_type,
                         :payload, :request_id, :correlation_id, :ip_address, :created_at)
                    """
                ),
                {
                    "id": event_id,
                    "event_type": event_type,
                    "actor_id": actor_id,
                    "actor_type": actor_type,
                    "aggregate_id": aggregate_id,
                    "aggregate_type": aggregate_type,
                    "payload": json.dumps(payload, default=str),
                    "request_id": request_id,
                    "correlation_id": correlation_id or aggregate_id,
                    "ip_address": ip_address,
                    "created_at": datetime.utcnow(),
                },
            )
        except Exception as exc:
            if best_effort:
                logger.warning(
                    "event_ledger: failed to log event_type=%s aggregate=%s/%s — %s",
                    event_type, aggregate_type, aggregate_id, exc,
                )
            else:
                raise

    @staticmethod
    def log_financial(
        db: Session,
        event_type: str,
        aggregate_id: str,
        aggregate_type: str,
        actor_id: str,
        amount: Any,
        currency: str,
        reference: str,
        extra: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Shorthand for financial events with standard payload structure."""
        payload: dict[str, Any] = {
            "amount": str(amount),
            "currency": currency,
            "reference": reference,
        }
        if extra:
            payload.update(extra)
        EventLedger.log(
            db=db,
            event_type=event_type,
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            actor_id=actor_id,
            payload=payload,
            **kwargs,
        )

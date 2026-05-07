from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from app.core.observability import get_request_id, logger

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass(frozen=True)
class AuditRecord:
    action: str
    user_id: str
    payment_id: str
    amount: Decimal
    currency: str
    provider: str
    status: str
    request_id: str
    timestamp: str
    transaction_id: str
    state_before: str
    state_after: str
    idempotency_key: str
    country_code: str


class FinancialAuditLogger:
    """
    Append-only financial audit logging.

    Always emits to the structured log stream.
    When a SQLAlchemy Session is provided, also persists to the
    financial_audit_logs table — failures are caught and logged so
    they never block the calling transaction.
    """

    @staticmethod
    def log(
        *,
        action: str,
        user_id: str,
        payment_id: str,
        amount: Decimal,
        currency: str,
        provider: str,
        status: str,
        transaction_id: str = "",
        state_before: str = "",
        state_after: str = "",
        request_id: str | None = None,
        idempotency_key: str = "",
        country_code: str = "",
        db: "Session | None" = None,
    ) -> AuditRecord:
        record = AuditRecord(
            action=action,
            user_id=user_id,
            payment_id=payment_id,
            amount=amount,
            currency=currency,
            provider=provider,
            status=status,
            request_id=request_id or get_request_id(),
            timestamp=datetime.now(timezone.utc).isoformat(),
            transaction_id=transaction_id or payment_id,
            state_before=state_before,
            state_after=state_after,
            idempotency_key=idempotency_key,
            country_code=country_code.upper(),
        )
        logger.info(
            "FIN_AUDIT action={} user_id={} payment_id={} transaction_id={} amount={} currency={} provider={} status={} state_before={} state_after={} idempotency_key={} country_code={} request_id={} timestamp={}",
            record.action,
            record.user_id,
            record.payment_id,
            record.transaction_id,
            record.amount,
            record.currency,
            record.provider,
            record.status,
            record.state_before,
            record.state_after,
            record.idempotency_key,
            record.country_code,
            record.request_id,
            record.timestamp,
        )

        if db is not None:
            try:
                import uuid as _uuid
                from app.models.audit_log import FinancialAuditLog
                entry = FinancialAuditLog(
                    id=str(_uuid.uuid4()),
                    action=record.action,
                    user_id=record.user_id,
                    payment_id=record.payment_id,
                    transaction_id=record.transaction_id,
                    amount=record.amount,
                    currency=record.currency,
                    provider=record.provider,
                    status=record.status,
                    state_before=record.state_before,
                    state_after=record.state_after,
                    idempotency_key=record.idempotency_key,
                    country_code=record.country_code,
                    request_id=record.request_id,
                    created_at=datetime.now(timezone.utc),
                )
                db.add(entry)
                db.commit()
            except Exception as exc:
                logger.error("FIN_AUDIT: DB persistence failed: {}", exc)
                try:
                    db.rollback()
                except Exception:
                    pass

        return record

from __future__ import annotations

from enum import Enum

from app.payment.audit_logger import FinancialAuditLogger


class TransactionState(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RECONCILING = "RECONCILING"
    REFUNDED = "REFUNDED"
    DISPUTED = "DISPUTED"
    REVERSED = "REVERSED"


class InvalidStateTransitionError(Exception):
    pass


ALLOWED_TRANSITIONS: dict[TransactionState, set[TransactionState]] = {
    TransactionState.PENDING: {TransactionState.PROCESSING, TransactionState.FAILED, TransactionState.RECONCILING},
    TransactionState.PROCESSING: {TransactionState.SUCCESS, TransactionState.FAILED, TransactionState.RECONCILING},
    TransactionState.SUCCESS: {
        TransactionState.PROCESSING, TransactionState.REFUNDED,
        TransactionState.RECONCILING, TransactionState.DISPUTED, TransactionState.REVERSED,
    },
    TransactionState.FAILED: {TransactionState.RECONCILING, TransactionState.DISPUTED},
    TransactionState.RECONCILING: {TransactionState.SUCCESS, TransactionState.FAILED, TransactionState.REFUNDED},
    TransactionState.REFUNDED: {TransactionState.DISPUTED},
    TransactionState.DISPUTED: {TransactionState.REVERSED, TransactionState.REFUNDED, TransactionState.RECONCILING},
    TransactionState.REVERSED: set(),
}


class TransactionStateMachine:
    @staticmethod
    def validate_transition(current: TransactionState, target: TransactionState) -> None:
        if target == current:
            return
        if target not in ALLOWED_TRANSITIONS[current]:
            raise InvalidStateTransitionError(f"Forbidden transition: {current.value} -> {target.value}")

    @staticmethod
    def transition(
        *,
        current: TransactionState,
        target: TransactionState,
        action: str,
        user_id: str,
        transaction_id: str,
        amount,
        currency: str,
        provider: str,
        request_id: str = "",
        idempotency_key: str = "",
        country_code: str = "",
    ) -> TransactionState:
        TransactionStateMachine.validate_transition(current, target)
        FinancialAuditLogger.log(
            action=action,
            user_id=user_id,
            payment_id=transaction_id,
            transaction_id=transaction_id,
            amount=amount,
            currency=currency,
            provider=provider,
            status=target.value.lower(),
            state_before=current.value,
            state_after=target.value,
            request_id=request_id or None,
            idempotency_key=idempotency_key,
            country_code=country_code,
        )
        return target

from __future__ import annotations

import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.payments.transaction_state_machine import TransactionState, TransactionStateMachine
from app.core.observability import logger
from app.models.wallet import Escrow, Transaction, Wallet
from app.payment.audit_logger import FinancialAuditLogger


def _uuid() -> str:
    return str(uuid.uuid4())


class InsufficientFundsError(Exception):
    pass


class WalletNotFoundError(Exception):
    pass


class EscrowError(Exception):
    pass


class LedgerDriftError(Exception):
    """Raised when wallet.balance diverges from the ledger-computed balance.

    The ledger (Transaction table) is the single source of truth.
    wallet.balance is a denormalized cache; it must always equal
    SUM(completed credits) - SUM(completed debits) for the wallet.
    """


class WalletService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _escrow_state(status: str) -> TransactionState:
        norm = (status or "").lower()
        if norm == "pending":
            return TransactionState.PENDING
        if norm in {"funded", "released"}:
            return TransactionState.SUCCESS
        if norm == "cancelled":
            return TransactionState.FAILED
        if norm == "refunded":
            return TransactionState.REFUNDED
        if norm == "processing":
            return TransactionState.PROCESSING
        return TransactionState.RECONCILING

    def _audit_transition(self, escrow: Escrow, target: TransactionState, action: str, provider: str) -> None:
        TransactionStateMachine.transition(
            current=self._escrow_state(escrow.status),
            target=target,
            action=action,
            user_id=escrow.payer_id,
            transaction_id=escrow.id,
            amount=escrow.amount,
            currency=escrow.currency,
            provider=provider,
        )

    # ─── Wallet CRUD ────────────────────────────────────────────────────────

    def create_wallet(self, user_id: str, currency: str) -> Wallet:
        existing = (
            self.db.execute(select(Wallet).where(Wallet.user_id == user_id, Wallet.currency == currency))
            .scalars()
            .one_or_none()
        )
        if existing:
            return existing

        wallet = Wallet(id=_uuid(), user_id=user_id, currency=currency, balance=Decimal("0"))
        self.db.add(wallet)
        try:
            self.db.commit()
        except IntegrityError:
            # Concurrent creation: another request won the INSERT race, return the winner.
            self.db.rollback()
            return (
                self.db.execute(select(Wallet).where(Wallet.user_id == user_id, Wallet.currency == currency))
                .scalars()
                .one()
            )
        self.db.refresh(wallet)
        return wallet

    def get_wallet(self, user_id: str, currency: str, *, for_update: bool = False) -> Wallet:
        stmt = select(Wallet).where(Wallet.user_id == user_id, Wallet.currency == currency)
        if for_update:
            stmt = stmt.with_for_update()
        wallet = self.db.execute(stmt).scalars().one_or_none()
        if wallet is None:
            raise WalletNotFoundError(f"Wallet {currency} introuvable pour user {user_id}")
        return wallet

    def get_balance(self, user_id: str, currency: str) -> Decimal:
        return self.get_wallet(user_id, currency).balance

    def get_escrow(self, escrow_id: str) -> Escrow:
        """Public read-only accessor — does not acquire a row lock."""
        return self._get_escrow(escrow_id)

    # ─── Balance operations ──────────────────────────────────────────────────

    def credit_wallet(
        self,
        user_id: str,
        currency: str,
        amount: Decimal,
        reference: str,
        provider: str = "internal",
        metadata: dict[str, Any] | None = None,
    ) -> Transaction:
        if amount <= Decimal("0"):
            raise ValueError("Le montant doit etre positif")

        # SELECT FOR UPDATE to prevent lost-update race on concurrent credits
        wallet = self._get_or_create_wallet(user_id, currency, for_update=True)

        # Idempotency guard: if a completed transaction with this reference already exists
        # for this wallet, return it without creating a duplicate (double-credit protection).
        existing_tx = self.db.execute(
            select(Transaction).where(
                Transaction.wallet_id == wallet.id,
                Transaction.reference == reference,
                Transaction.type == "credit",
            )
        ).scalars().one_or_none()
        if existing_tx is not None:
            logger.warning(
                "credit_wallet: duplicate reference=%s wallet=%s — returning existing tx %s",
                reference, wallet.id, existing_tx.id,
            )
            return existing_tx

        tx = Transaction(
            id=_uuid(),
            wallet_id=wallet.id,
            type="credit",
            amount=amount,
            status="completed",
            reference=reference,
            provider=provider,
            metadata_json=json.dumps(metadata) if metadata else None,
        )
        wallet.balance += amount
        self.db.add(tx)
        self.db.commit()
        self.db.refresh(tx)
        return tx

    def debit_wallet(
        self,
        user_id: str,
        currency: str,
        amount: Decimal,
        reference: str,
        provider: str = "internal",
        metadata: dict[str, Any] | None = None,
    ) -> Transaction:
        if amount <= Decimal("0"):
            raise ValueError("Le montant doit etre positif")

        wallet = self.get_wallet(user_id, currency, for_update=True)

        # Idempotency guard: prevent double-debit on the same reference.
        existing_tx = self.db.execute(
            select(Transaction).where(
                Transaction.wallet_id == wallet.id,
                Transaction.reference == reference,
                Transaction.type == "debit",
            )
        ).scalars().one_or_none()
        if existing_tx is not None:
            logger.warning(
                "debit_wallet: duplicate reference=%s wallet=%s — returning existing tx %s",
                reference, wallet.id, existing_tx.id,
            )
            return existing_tx

        if wallet.balance < amount:
            raise InsufficientFundsError(f"Solde insuffisant : {wallet.balance} {currency} < {amount} {currency}")

        tx = Transaction(
            id=_uuid(),
            wallet_id=wallet.id,
            type="debit",
            amount=amount,
            status="completed",
            reference=reference,
            provider=provider,
            metadata_json=json.dumps(metadata) if metadata else None,
        )
        wallet.balance -= amount
        self.db.add(tx)
        self.db.commit()
        self.db.refresh(tx)
        return tx

    # ─── Escrow lifecycle ────────────────────────────────────────────────────

    def create_escrow(self, task_id: str, payer_id: str, payee_id: str | None, amount: Decimal, currency: str) -> Escrow:
        if amount <= Decimal("0"):
            raise ValueError("Le montant escrow doit etre positif")

        # P1-008 FIX: Idempotency guard — return existing active escrow if one already
        # exists for this task.  Without this, two concurrent POST /wallet/escrow calls
        # for the same task_id both succeed and create two funded escrows.  The second
        # escrow is never linked to a release → funds locked forever.
        # We lock the existing row (FOR UPDATE) to prevent a concurrent create from
        # slipping through the gap between this check and the INSERT below.
        existing = self.db.execute(
            select(Escrow).where(
                Escrow.task_id == task_id,
                Escrow.status.in_(["funded", "hold", "pending"]),
            ).with_for_update(skip_locked=False)
        ).scalars().one_or_none()
        if existing is not None:
            logger.warning(
                "create_escrow: active escrow already exists task=%s escrow=%s status=%s — returning existing",
                task_id, existing.id, existing.status,
            )
            return existing

        escrow_id = _uuid()

        # Acquire row-lock on wallet BEFORE any write — prevents concurrent double-spend.
        wallet = self.get_wallet(payer_id, currency, for_update=True)
        if wallet.balance < amount:
            raise InsufficientFundsError(
                f"Solde insuffisant : {wallet.balance} {currency} < {amount} {currency}"
            )

        # Build debit TX and Escrow in a SINGLE commit to avoid the two-phase gap
        # (old code: debit_wallet committed, then crash before escrow commit → funds lost).
        tx = Transaction(
            id=_uuid(),
            wallet_id=wallet.id,
            type="debit",
            amount=amount,
            status="completed",
            reference=f"escrow_fund:{escrow_id}",
            provider="internal",
            metadata_json=json.dumps({"type": "escrow_fund", "escrow_id": escrow_id, "task_id": task_id}),
        )
        wallet.balance -= amount
        self.db.add(tx)
        self.db.flush()  # assigns tx.id without committing

        escrow = Escrow(
            id=escrow_id,
            task_id=task_id,
            payer_id=payer_id,
            payee_id=payee_id,
            amount=amount,
            currency=currency,
            status="funded",
            funding_tx_id=tx.id,
        )
        self.db.add(escrow)
        self.db.commit()  # single atomic commit — wallet debit + escrow creation
        self.db.refresh(escrow)
        return escrow

    def release_escrow(self, escrow_id: str) -> Escrow:
        from app.core.config import settings as _cfg
        escrow = self._get_escrow(escrow_id, for_update=True)
        # Accept "hold" too: scheduler auto-releases escrows in hold state after 6h window.
        if escrow.status not in {"funded", "hold"}:
            raise EscrowError(f"Escrow {escrow_id} ne peut etre libere (statut: {escrow.status})")
        if not escrow.payee_id:
            raise EscrowError(f"Escrow {escrow_id} n'a pas de payee defini")

        self._audit_transition(escrow, TransactionState.PROCESSING, "release_processing", "internal")

        # ZASKA 15% commission
        commission_bps = _cfg.zaska_commission_bps
        commission = (escrow.amount * Decimal(str(commission_bps)) / Decimal("10000")).quantize(Decimal("0.000001"))
        tasker_amount = escrow.amount - commission

        # Credit tasker (85%)
        wallet = self._get_or_create_wallet(escrow.payee_id, escrow.currency, for_update=True)
        tx = Transaction(
            id=_uuid(),
            wallet_id=wallet.id,
            type="credit",
            amount=tasker_amount,
            status="completed",
            reference=f"escrow_release:{escrow_id}",
            provider="internal",
            metadata_json=json.dumps({
                "escrow_id": escrow_id, "task_id": escrow.task_id,
                "gross": str(escrow.amount), "commission_bps": commission_bps,
                "commission": str(commission), "net": str(tasker_amount),
            }),
        )
        wallet.balance += tasker_amount
        self.db.add(tx)
        self.db.flush()

        # Credit ZASKA commission wallet (15%)
        zaska_user_id = _cfg.zaska_wallet_user_id
        if commission > Decimal("0") and zaska_user_id:
            zaska_wallet = self._get_or_create_wallet(zaska_user_id, escrow.currency, for_update=True)
            zaska_tx = Transaction(
                id=_uuid(),
                wallet_id=zaska_wallet.id,
                type="credit",
                amount=commission,
                status="completed",
                reference=f"commission:{escrow_id}",
                provider="internal",
                metadata_json=json.dumps({"escrow_id": escrow_id, "task_id": escrow.task_id, "type": "zaska_commission"}),
            )
            zaska_wallet.balance += commission
            self.db.add(zaska_tx)
        elif commission > Decimal("0"):
            logger.warning("ZASKA_WALLET_USER_ID not configured — commission {} {} not credited", commission, escrow.currency)

        escrow.status = "released"
        escrow.settlement_tx_id = tx.id
        # Append immutable audit event before commit (same transaction)
        try:
            from app.services.event_ledger import EventLedger
            EventLedger.log_financial(
                db=self.db,
                event_type="escrow.released",
                aggregate_id=escrow_id,
                aggregate_type="escrow",
                actor_id=escrow.payee_id or "",
                amount=escrow.amount,
                currency=escrow.currency,
                reference=f"escrow_release:{escrow_id}",
                extra={
                    "task_id": escrow.task_id,
                    "commission_bps": commission_bps,
                    "commission": str(commission),
                    "tasker_amount": str(tasker_amount),
                },
            )
        except Exception as _ledger_exc:
            # AUDIT-04 FIX: log instead of silently swallowing.
            # A missing audit event is a compliance issue — alert so ops can investigate.
            logger.error(
                "AUDIT_TRAIL_FAILURE: EventLedger.log_financial failed for escrow=%s — %s",
                escrow_id, _ledger_exc,
            )
        self.db.commit()
        self.db.refresh(escrow)
        return escrow

    def refund_escrow(self, escrow_id: str) -> Escrow:
        escrow = self._get_escrow(escrow_id, for_update=True)
        # Accept "hold" too: escrow enters hold when tasker declares complete (6h window).
        # Admin cancel or tasker abandon during hold must still be refundable.
        if escrow.status not in {"funded", "hold"}:
            raise EscrowError(f"Escrow {escrow_id} ne peut etre rembourse (statut: {escrow.status})")

        self._audit_transition(escrow, TransactionState.REFUNDED, "refund_processing", "internal")

        # Inline credit — single commit encompasses both wallet update and escrow status change.
        wallet = self._get_or_create_wallet(escrow.payer_id, escrow.currency, for_update=True)
        tx = Transaction(
            id=_uuid(),
            wallet_id=wallet.id,
            type="credit",
            amount=escrow.amount,
            status="completed",
            reference=f"escrow_refund:{escrow_id}",
            provider="internal",
            metadata_json=json.dumps({"escrow_id": escrow_id, "task_id": escrow.task_id}),
        )
        wallet.balance += escrow.amount
        self.db.add(tx)
        self.db.flush()  # obtain tx.id before commit

        escrow.status = "refunded"
        escrow.settlement_tx_id = tx.id
        self.db.commit()  # single atomic commit
        self.db.refresh(escrow)
        return escrow

    def create_pending_escrow(self, task_id: str, payer_id: str, payee_id: str | None, amount: Decimal, currency: str) -> Escrow:
        if amount <= Decimal("0"):
            raise ValueError("Le montant escrow doit etre positif")

        escrow = Escrow(
            id=_uuid(),
            task_id=task_id,
            payer_id=payer_id,
            payee_id=payee_id,
            amount=amount,
            currency=currency,
            status="pending",
        )
        self.db.add(escrow)
        self.db.commit()
        self.db.refresh(escrow)
        FinancialAuditLogger.log(
            action="create_escrow",
            user_id=payer_id,
            payment_id=escrow.id,
            transaction_id=escrow.id,
            amount=amount,
            currency=currency,
            provider="internal",
            status=escrow.status,
            state_before="",
            state_after=TransactionState.PENDING.value,
        )
        return escrow

    def fund_escrow_from_payment(self, escrow_id: str, provider: str, provider_tx_id: str) -> Escrow:
        """Mark escrow as funded from an EXTERNAL payment (Stripe/FedaPay/Flutterwave).

        Does NOT touch the payer's wallet balance — the money arrived externally.
        Only the escrow status and provider reference are updated.
        """
        escrow = self._get_escrow(escrow_id, for_update=True)
        if escrow.status == "funded":
            logger.warning("double_payment_detected escrow_id={} provider={} provider_tx_id={}", escrow_id, provider, provider_tx_id)
            return escrow
        if escrow.status != "pending":
            raise EscrowError(f"Escrow {escrow_id} ne peut etre finance (statut: {escrow.status})")

        self._audit_transition(escrow, TransactionState.PROCESSING, "payment_processing", provider)

        escrow.status = "funded"
        escrow.provider = provider
        escrow.provider_tx_id = provider_tx_id
        self.db.commit()
        self.db.refresh(escrow)
        FinancialAuditLogger.log(
            action="confirm_payment",
            user_id=escrow.payer_id,
            payment_id=escrow.id,
            transaction_id=escrow.id,
            amount=escrow.amount,
            currency=escrow.currency,
            provider=provider,
            status=escrow.status,
            state_before=TransactionState.PROCESSING.value,
            state_after=TransactionState.SUCCESS.value,
        )
        return escrow

    def cancel_pending_escrow(self, escrow_id: str) -> Escrow:
        escrow = self._get_escrow(escrow_id, for_update=True)
        if escrow.status == "cancelled":
            return escrow
        if escrow.status != "pending":
            raise EscrowError(f"Escrow {escrow_id} ne peut etre annule (statut: {escrow.status})")

        self._audit_transition(escrow, TransactionState.FAILED, "payment_failed", "internal")
        escrow.status = "cancelled"
        self.db.commit()
        self.db.refresh(escrow)
        FinancialAuditLogger.log(
            action="cancel_escrow",
            user_id=escrow.payer_id,
            payment_id=escrow.id,
            transaction_id=escrow.id,
            amount=escrow.amount,
            currency=escrow.currency,
            provider="internal",
            status=escrow.status,
            state_before=TransactionState.PENDING.value,
            state_after=TransactionState.FAILED.value,
        )
        return escrow

    def lock_funds(self, escrow_id: str) -> Escrow:
        """Acquire a row lock on the escrow to prevent concurrent double-processing."""
        return self._get_escrow(escrow_id, for_update=True)

    def release_escrow_safe(self, escrow_id: str) -> Escrow:
        escrow = self.release_escrow(escrow_id)
        FinancialAuditLogger.log(
            action="release_escrow",
            user_id=escrow.payee_id or "",
            payment_id=escrow.id,
            transaction_id=escrow.id,
            amount=escrow.amount,
            currency=escrow.currency,
            provider="internal",
            status=escrow.status,
            state_before=TransactionState.PROCESSING.value,
            state_after=TransactionState.SUCCESS.value,
        )
        return escrow

    def finalize_transaction(self, escrow_id: str) -> Escrow:
        escrow = self._get_escrow(escrow_id)
        FinancialAuditLogger.log(
            action="finalize_transaction",
            user_id=escrow.payer_id,
            payment_id=escrow.id,
            transaction_id=escrow.id,
            amount=escrow.amount,
            currency=escrow.currency,
            provider="internal",
            status=escrow.status,
        )
        return escrow

    def get_escrow_by_task(self, task_id: str) -> Escrow | None:
        return self.db.execute(select(Escrow).where(Escrow.task_id == task_id)).scalars().one_or_none()

    def get_escrow_by_task_for_update(self, task_id: str) -> Escrow | None:
        """Like get_escrow_by_task but acquires a row lock — use inside critical sections
        where the escrow status must not change between read and write (FIN-03)."""
        return (
            self.db.execute(
                select(Escrow).where(Escrow.task_id == task_id).with_for_update()
            )
            .scalars()
            .one_or_none()
        )

    def hold_escrow_24h(self, escrow_id: str) -> Escrow:
        """Transition funded → hold: starts the 6h contestation window."""
        from datetime import timedelta
        escrow = self._get_escrow(escrow_id, for_update=True)
        if escrow.status != "funded":
            raise EscrowError(f"Escrow {escrow_id} ne peut passer en hold (statut: {escrow.status})")
        escrow.status = "hold"
        # Use naive UTC — DB column is TIMESTAMP WITHOUT TIME ZONE.
        # contest_escrow and release_held_escrow compare with datetime.utcnow() (naive),
        # so we must be consistent here to avoid TypeError on comparison.
        escrow.payout_available_at = datetime.utcnow() + timedelta(hours=6)
        self.db.commit()
        self.db.refresh(escrow)
        return escrow

    def hold_escrow_6h(self, escrow_id: str) -> Escrow:
        """Alias for hold_escrow_24h — 6h contestation window."""
        return self.hold_escrow_24h(escrow_id)

    def contest_escrow(self, escrow_id: str, client_user_id: str) -> Escrow:
        """Client contests the work — freezes payment during 6h hold window."""
        from datetime import timedelta
        # Use naive UTC — DB column is TIMESTAMP WITHOUT TIME ZONE; comparing aware vs naive raises TypeError
        now = datetime.utcnow()
        escrow = self._get_escrow(escrow_id, for_update=True)
        if escrow.payer_id != client_user_id:
            raise EscrowError("Seul le payeur peut contester cet escrow")
        if escrow.status != "hold":
            raise EscrowError(f"Escrow {escrow_id} ne peut être contesté (statut: {escrow.status})")
        if escrow.payout_available_at and now > escrow.payout_available_at:
            raise EscrowError("La fenêtre de contestation de 6h est expirée")
        escrow.status = "contested"
        escrow.contested_at = now
        self.db.commit()
        self.db.refresh(escrow)
        return escrow

    def release_held_escrow(self, escrow_id: str) -> Escrow:
        """Release escrow after 24h hold has passed (no contest).

        P0-005 FIX: Do NOT call self.release_escrow() here — that would issue a second
        SELECT FOR UPDATE on the same row in the same transaction, which is wasteful and
        potentially inconsistent (release_escrow would re-read the row, possibly getting
        a cached/stale SQLAlchemy identity map entry).

        Instead, inline the release logic directly on the already-locked escrow.
        """
        from app.core.config import settings as _cfg
        now = datetime.utcnow()
        escrow = self._get_escrow(escrow_id, for_update=True)

        if escrow.status != "hold":
            raise EscrowError(f"Escrow {escrow_id} n'est pas en hold (statut: {escrow.status})")
        if escrow.payout_available_at and now < escrow.payout_available_at:
            remaining = int((escrow.payout_available_at - now).total_seconds() / 3600)
            raise EscrowError(f"Paiement disponible dans ~{remaining}h — la période de contestation n'est pas terminée")
        if not escrow.payee_id:
            raise EscrowError(f"Escrow {escrow_id} n'a pas de payee défini")

        self._audit_transition(escrow, TransactionState.PROCESSING, "release_processing", "internal")

        commission_bps = _cfg.zaska_commission_bps
        commission = (escrow.amount * Decimal(str(commission_bps)) / Decimal("10000")).quantize(Decimal("0.000001"))
        tasker_amount = escrow.amount - commission

        wallet = self._get_or_create_wallet(escrow.payee_id, escrow.currency, for_update=True)
        tx = Transaction(
            id=_uuid(),
            wallet_id=wallet.id,
            type="credit",
            amount=tasker_amount,
            status="completed",
            reference=f"escrow_release:{escrow_id}",
            provider="internal",
            metadata_json=json.dumps({
                "escrow_id": escrow_id, "task_id": escrow.task_id,
                "gross": str(escrow.amount), "commission_bps": commission_bps,
                "commission": str(commission), "net": str(tasker_amount),
                "source": "hold_auto_release",
            }),
        )
        wallet.balance += tasker_amount
        self.db.add(tx)
        self.db.flush()

        zaska_user_id = _cfg.zaska_wallet_user_id
        if commission > Decimal("0") and zaska_user_id:
            zaska_wallet = self._get_or_create_wallet(zaska_user_id, escrow.currency, for_update=True)
            zaska_tx = Transaction(
                id=_uuid(),
                wallet_id=zaska_wallet.id,
                type="credit",
                amount=commission,
                status="completed",
                reference=f"commission:{escrow_id}",
                provider="internal",
                metadata_json=json.dumps({"escrow_id": escrow_id, "type": "zaska_commission"}),
            )
            zaska_wallet.balance += commission
            self.db.add(zaska_tx)

        escrow.status = "released"
        escrow.settlement_tx_id = tx.id
        self.db.commit()
        self.db.refresh(escrow)
        return escrow

    def partial_release_escrow(self, escrow_id: str, completion_percent: int) -> tuple[Escrow, Decimal, Decimal]:
        """Fixed split on partial task abandonment/completion:
        Tasker 10%, ZASKA 5%, Client 85%. completion_percent is recorded only.

        Returns (escrow, executor_amount, client_refund).
        """
        from app.core.config import settings as _cfg
        escrow = self._get_escrow(escrow_id, for_update=True)
        if escrow.status not in {"funded", "hold"}:
            raise EscrowError(f"Escrow {escrow_id} ne peut être libéré partiellement (statut: {escrow.status})")
        if not escrow.payee_id:
            raise EscrowError(f"Escrow {escrow_id} n'a pas d'exécutant défini")

        # Fixed split: tasker 10%, ZASKA 5%, client 85%
        executor_amount = (escrow.amount * Decimal("10") / Decimal("100")).quantize(Decimal("0.000001"))
        zaska_commission = (escrow.amount * Decimal("5") / Decimal("100")).quantize(Decimal("0.000001"))
        client_refund = escrow.amount - executor_amount - zaska_commission

        meta_base = {
            "escrow_id": escrow_id, "task_id": escrow.task_id,
            "completion_percent": completion_percent,
            "gross": str(escrow.amount), "tasker_pct": 10, "zaska_pct": 5, "client_pct": 85,
        }

        # Credit executor (10%)
        exec_wallet = self._get_or_create_wallet(escrow.payee_id, escrow.currency, for_update=True)
        exec_tx = Transaction(
            id=_uuid(),
            wallet_id=exec_wallet.id,
            type="credit",
            amount=executor_amount,
            status="completed",
            reference=f"partial_release:{escrow_id}",
            provider="internal",
            metadata_json=json.dumps({**meta_base, "type": "partial_payment"}),
        )
        exec_wallet.balance += executor_amount
        self.db.add(exec_tx)

        # Credit ZASKA (5%)
        zaska_user_id = _cfg.zaska_wallet_user_id
        if zaska_commission > Decimal("0") and zaska_user_id:
            zaska_wallet = self._get_or_create_wallet(zaska_user_id, escrow.currency, for_update=True)
            zaska_tx = Transaction(
                id=_uuid(),
                wallet_id=zaska_wallet.id,
                type="credit",
                amount=zaska_commission,
                status="completed",
                reference=f"partial_commission:{escrow_id}",
                provider="internal",
                metadata_json=json.dumps({**meta_base, "type": "zaska_commission"}),
            )
            zaska_wallet.balance += zaska_commission
            self.db.add(zaska_tx)

        # Refund client (85%)
        payer_wallet = self._get_or_create_wallet(escrow.payer_id, escrow.currency, for_update=True)
        refund_tx = Transaction(
            id=_uuid(),
            wallet_id=payer_wallet.id,
            type="credit",
            amount=client_refund,
            status="completed",
            reference=f"partial_refund:{escrow_id}",
            provider="internal",
            metadata_json=json.dumps({**meta_base, "type": "partial_refund"}),
        )
        payer_wallet.balance += client_refund
        self.db.add(refund_tx)
        self.db.flush()

        escrow.status = "partial_released"
        escrow.settlement_tx_id = exec_tx.id
        self.db.commit()
        self.db.refresh(escrow)

        FinancialAuditLogger.log(
            action="partial_release_escrow",
            user_id=escrow.payee_id,
            payment_id=escrow.id,
            transaction_id=exec_tx.id,
            amount=executor_amount,
            currency=escrow.currency,
            provider="internal",
            status="partial_released",
        )
        return escrow, executor_amount, client_refund

    def list_wallets(self, user_id: str) -> list[Wallet]:
        """Return all wallets for a user across all currencies."""
        return (
            self.db.execute(select(Wallet).where(Wallet.user_id == user_id).order_by(Wallet.currency))
            .scalars()
            .all()
        )

    def list_transactions(self, user_id: str, currency: str, limit: int = 50, offset: int = 0) -> list[Transaction]:
        wallet = self.get_wallet(user_id, currency)
        return (
            self.db.execute(
                select(Transaction)
                .where(Transaction.wallet_id == wallet.id)
                .order_by(Transaction.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )

    # ─── FX Conversion ──────────────────────────────────────────────────────

    def convert_currency(
        self,
        user_id: str,
        from_currency: str,
        to_currency: str,
        from_amount: Decimal,
        rate: Decimal,
        fee_bps: int = 0,
        reference: str | None = None,
    ) -> tuple[Transaction, Transaction]:
        """
        Converts from_amount from from_currency to to_currency at the given rate.
        Fee is deducted from the converted amount (to_amount).
        Both debit and credit are atomic within a single DB commit.

        Returns (debit_tx, credit_tx).
        Raises InsufficientFundsError if source balance is too low.
        """
        if from_amount <= Decimal("0"):
            raise ValueError("Le montant à convertir doit être positif")
        if rate <= Decimal("0"):
            raise ValueError("Le taux de conversion doit être positif")

        to_amount_gross = (from_amount * rate).quantize(Decimal("0.000001"))
        fee_amount = (to_amount_gross * Decimal(fee_bps) / Decimal(10000)).quantize(Decimal("0.000001"))
        to_amount = to_amount_gross - fee_amount

        if to_amount <= Decimal("0"):
            raise ValueError("Montant converti nul après frais — augmenter le montant")

        ref = reference or f"fx:{from_currency}:{to_currency}:{_uuid()}"

        # Canonical lock ordering for FX wallets of the SAME user.
        # Even same-user wallets must be locked in deterministic order to prevent
        # deadlocks when the same user issues concurrent FX conversions in both directions.
        first_currency, second_currency = sorted([from_currency, to_currency])
        if first_currency == from_currency:
            from_wallet = self.get_wallet(user_id, from_currency, for_update=True)
            to_wallet = self._get_or_create_wallet(user_id, to_currency, for_update=True)
        else:
            to_wallet = self._get_or_create_wallet(user_id, to_currency, for_update=True)
            from_wallet = self.get_wallet(user_id, from_currency, for_update=True)

        if from_wallet.balance < from_amount:
            raise InsufficientFundsError(
                f"Solde insuffisant : {from_wallet.balance} {from_currency} < {from_amount}"
            )

        debit_tx = Transaction(
            id=_uuid(),
            wallet_id=from_wallet.id,
            type="debit",
            amount=from_amount,
            status="completed",
            reference=f"{ref}:debit",
            provider="internal",
            metadata_json=json.dumps({
                "type": "fx_conversion",
                "from_currency": from_currency,
                "to_currency": to_currency,
                "rate": str(rate),
                "fee_bps": fee_bps,
                "to_amount": str(to_amount),
            }),
        )
        from_wallet.balance -= from_amount
        self.db.add(debit_tx)

        credit_tx = Transaction(
            id=_uuid(),
            wallet_id=to_wallet.id,
            type="credit",
            amount=to_amount,
            status="completed",
            reference=f"{ref}:credit",
            provider="internal",
            metadata_json=json.dumps({
                "type": "fx_conversion",
                "from_currency": from_currency,
                "to_currency": to_currency,
                "rate": str(rate),
                "fee_bps": fee_bps,
                "from_amount": str(from_amount),
            }),
        )
        to_wallet.balance += to_amount
        self.db.add(credit_tx)

        self.db.commit()
        self.db.refresh(debit_tx)
        self.db.refresh(credit_tx)

        return debit_tx, credit_tx

    # ─── Ledger reconciliation ────────────────────────────────────────────────

    def recompute_balance_from_ledger(self, user_id: str, currency: str) -> Decimal:
        """
        Compute the correct wallet balance from the immutable Transaction ledger.

        Balance = SUM(completed credits) − SUM(completed debits)

        This is the ground truth. wallet.balance is a denormalized cache that
        must always equal this value. If they diverge, use this value to correct
        wallet.balance — the ledger is never wrong, the cache may be stale.
        """
        wallet = self.get_wallet(user_id, currency)
        result = self.db.execute(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (Transaction.type == "credit", Transaction.amount),
                            else_=Decimal("0"),
                        )
                    ),
                    Decimal("0"),
                )
                - func.coalesce(
                    func.sum(
                        case(
                            (Transaction.type == "debit", Transaction.amount),
                            else_=Decimal("0"),
                        )
                    ),
                    Decimal("0"),
                )
            ).where(
                Transaction.wallet_id == wallet.id,
                Transaction.status == "completed",
            )
        ).scalar()
        return Decimal(str(result)) if result is not None else Decimal("0")

    def assert_ledger_consistent(self, user_id: str, currency: str) -> None:
        """
        Raise LedgerDriftError if wallet.balance != ledger-computed balance.

        Call this in health checks or after suspicious balance operations.
        Under no condition should the provider or cache layer be authoritative.
        """
        wallet = self.get_wallet(user_id, currency)
        computed = self.recompute_balance_from_ledger(user_id, currency)
        diff = abs(wallet.balance - computed)
        if diff > Decimal("0.000001"):
            raise LedgerDriftError(
                f"Ledger drift: user={user_id} currency={currency} "
                f"wallet.balance={wallet.balance} ledger_computed={computed} diff={diff}"
            )

    # ─── Private helpers ─────────────────────────────────────────────────────

    def _get_or_create_wallet(self, user_id: str, currency: str, *, for_update: bool = False) -> Wallet:
        stmt = select(Wallet).where(Wallet.user_id == user_id, Wallet.currency == currency)
        if for_update:
            stmt = stmt.with_for_update()
        wallet = self.db.execute(stmt).scalars().one_or_none()
        if wallet is None:
            new_wallet = Wallet(id=_uuid(), user_id=user_id, currency=currency, balance=Decimal("0"))
            self.db.add(new_wallet)
            try:
                # Use a SAVEPOINT so a concurrent-creation IntegrityError only rolls back
                # the INSERT — NOT the entire outer transaction (which may have staged
                # wallet credits via flush() that must not be lost).
                with self.db.begin_nested():
                    self.db.flush()
                wallet = new_wallet
            except IntegrityError:
                # Another request won the INSERT race; discard our failed object and
                # re-read the winner.  Outer transaction is intact (savepoint rolled back).
                self.db.expunge(new_wallet)
                wallet = self.db.execute(
                    select(Wallet).where(Wallet.user_id == user_id, Wallet.currency == currency)
                ).scalars().one()
        return wallet

    def _get_escrow(self, escrow_id: str, *, for_update: bool = False) -> Escrow:
        stmt = select(Escrow).where(Escrow.id == escrow_id)
        if for_update:
            stmt = stmt.with_for_update()
        escrow = self.db.execute(stmt).scalars().one_or_none()
        if escrow is None:
            logger.error("escrow_missing escrow_id={}", escrow_id)
            raise EscrowError(f"Escrow {escrow_id} introuvable")
        return escrow

    # ─── Withdrawal ──────────────────────────────────────────────────────────

    def withdraw(
        self,
        user_id: str,
        amount: Decimal,
        currency: str,
        provider: str,
        phone_number: str,
        country_code: str,
    ) -> dict:
        if amount <= Decimal("0"):
            raise ValueError("Le montant doit être positif")

        reference = f"withdraw:{_uuid()}"
        tx = self.debit_wallet(
            user_id=user_id,
            currency=currency,
            amount=amount,
            reference=reference,
            provider=provider,
            metadata={
                "type": "withdrawal",
                "provider": provider,
                "phone_number": phone_number,
                "country_code": country_code,
            },
        )
        return {
            "tx_id": tx.id,
            "status": "completed",
            "amount": str(amount),
            "currency": currency,
            "provider": provider,
            "phone_number": phone_number,
            "reference": reference,
        }

    # ─── Dispute & Reversal ──────────────────────────────────────────────────

    def transfer_atomic(
        self,
        from_user_id: str,
        to_user_id: str,
        currency: str,
        amount: Decimal,
        reference: str,
        note: str = "",
    ) -> tuple[Transaction, Transaction]:
        """
        Atomic transfer between two users — single DB commit.
        Verifies recipient exists, locks both wallets, creates both transactions atomically.
        Raises ValueError if recipient doesn't exist.
        Raises InsufficientFundsError if sender has insufficient funds.

        Deadlock prevention: wallets are always locked in alphabetical user_id order.
        Two concurrent transfers A→B and B→A will both acquire locks in the same order,
        eliminating the cycle that would cause a PostgreSQL deadlock.
        """
        from app.models.user import User

        if amount <= Decimal("0"):
            raise ValueError("Le montant doit être positif")

        recipient = self.db.get(User, to_user_id)
        if recipient is None:
            raise ValueError(f"Utilisateur destinataire {to_user_id} introuvable")

        # Canonical lock ordering — always lock by user_id alphabetically to prevent deadlock
        first_id, second_id = sorted([from_user_id, to_user_id])
        first_wallet = self.get_wallet(first_id, currency, for_update=True)
        second_wallet = self._get_or_create_wallet(second_id, currency, for_update=True)

        from_wallet = first_wallet if first_id == from_user_id else second_wallet
        to_wallet = second_wallet if second_id == to_user_id else first_wallet

        if from_wallet.balance < amount:
            raise InsufficientFundsError(
                f"Solde insuffisant : {from_wallet.balance} {currency} < {amount} {currency}"
            )

        debit_tx = Transaction(
            id=_uuid(),
            wallet_id=from_wallet.id,
            type="debit",
            amount=amount,
            status="completed",
            reference=f"transfer_out:{reference}",
            provider="internal",
            metadata_json=json.dumps({"type": "transfer_out", "to_user_id": to_user_id, "note": note}),
        )
        credit_tx = Transaction(
            id=_uuid(),
            wallet_id=to_wallet.id,
            type="credit",
            amount=amount,
            status="completed",
            reference=f"transfer_in:{reference}",
            provider="internal",
            metadata_json=json.dumps({"type": "transfer_in", "from_user_id": from_user_id, "note": note}),
        )

        from_wallet.balance -= amount
        to_wallet.balance += amount
        self.db.add(debit_tx)
        self.db.add(credit_tx)
        self.db.commit()
        self.db.refresh(debit_tx)
        self.db.refresh(credit_tx)

        FinancialAuditLogger.log(
            action="transfer",
            user_id=from_user_id,
            payment_id=reference,
            amount=amount,
            currency=currency,
            provider="internal",
            status="completed",
        )
        return debit_tx, credit_tx

    def reverse_transaction(
        self,
        transaction_id: str,
        reason: str,
        admin_user_id: str,
    ) -> tuple[Transaction, "DisputeRecord"]:
        """
        Reverse a completed transaction.
        - Creates the counter-transaction (credit→debit or debit→credit).
        - Marks the original transaction status = 'reversed'.
        - Creates a DisputeRecord(dispute_type='reversal').
        Raises ValueError if the transaction cannot be reversed.
        """
        from app.models.dispute import DisputeRecord

        orig = self.db.execute(
            select(Transaction).where(Transaction.id == transaction_id).with_for_update()
        ).scalars().one_or_none()
        if orig is None:
            raise ValueError(f"Transaction {transaction_id} introuvable")
        if orig.status == "reversed":
            raise ValueError(f"Transaction {transaction_id} déjà annulée")
        if orig.status != "completed":
            raise ValueError(
                f"Transaction {transaction_id} ne peut être annulée (statut: {orig.status}) — seules les transactions completed sont reversibles"
            )

        wallet = self.db.execute(
            select(Wallet).where(Wallet.id == orig.wallet_id).with_for_update()
        ).scalars().one_or_none()
        if wallet is None:
            raise ValueError("Wallet introuvable pour cette transaction")

        rev_type = "credit" if orig.type == "debit" else "debit"
        rev_ref = f"reversal:{transaction_id}"

        if rev_type == "credit":
            wallet.balance += orig.amount
        else:
            if wallet.balance < orig.amount:
                raise InsufficientFundsError(
                    f"Solde insuffisant pour annuler: {wallet.balance} < {orig.amount}"
                )
            wallet.balance -= orig.amount

        rev_tx = Transaction(
            id=_uuid(),
            wallet_id=orig.wallet_id,
            type=rev_type,
            amount=orig.amount,
            status="completed",
            reference=rev_ref,
            provider="internal",
            metadata_json=json.dumps({
                "type": "reversal",
                "original_tx_id": transaction_id,
                "reason": reason,
                "admin_user_id": admin_user_id,
            }),
        )
        self.db.add(rev_tx)
        self.db.flush()

        orig.status = "reversed"

        dispute = DisputeRecord(
            id=_uuid(),
            user_id=wallet.user_id,
            transaction_id=transaction_id,
            dispute_type="reversal",
            reason=reason,
            status="resolved",
            admin_notes=f"Reversed by admin {admin_user_id}",
            resolution_tx_id=rev_tx.id,
        )
        self.db.add(dispute)
        self.db.commit()
        self.db.refresh(rev_tx)
        self.db.refresh(dispute)

        FinancialAuditLogger.log(
            action="transaction_reversed",
            user_id=admin_user_id,
            payment_id=transaction_id,
            transaction_id=rev_tx.id,
            amount=orig.amount,
            currency="",
            provider="internal",
            status="reversed",
            state_before="completed",
            state_after="reversed",
        )
        return rev_tx, dispute

    def open_dispute(
        self,
        user_id: str,
        reason: str,
        dispute_type: str = "dispute",
        transaction_id: str | None = None,
        payout_id: str | None = None,
    ) -> "DisputeRecord":
        from app.models.dispute import DisputeRecord

        if not transaction_id and not payout_id:
            raise ValueError("transaction_id ou payout_id requis pour ouvrir un litige")

        dispute = DisputeRecord(
            id=_uuid(),
            user_id=user_id,
            transaction_id=transaction_id,
            payout_id=payout_id,
            dispute_type=dispute_type,
            reason=reason,
            status="open",
        )
        self.db.add(dispute)
        self.db.commit()
        self.db.refresh(dispute)

        FinancialAuditLogger.log(
            action="dispute_opened",
            user_id=user_id,
            payment_id=transaction_id or payout_id or "",
            amount=Decimal("0"),
            currency="",
            provider="internal",
            status="open",
        )
        return dispute

    def resolve_dispute(
        self,
        dispute_id: str,
        admin_user_id: str,
        resolution: str,
        admin_notes: str = "",
    ) -> "DisputeRecord":
        """resolution = 'resolved' | 'rejected'"""
        from app.models.dispute import DisputeRecord

        dispute = self.db.execute(
            select(DisputeRecord).where(DisputeRecord.id == dispute_id).with_for_update()
        ).scalars().one_or_none()
        if dispute is None:
            raise ValueError(f"Litige {dispute_id} introuvable")
        if dispute.status != "open":
            raise ValueError(f"Litige {dispute_id} déjà traité (statut: {dispute.status})")
        if resolution not in {"resolved", "rejected"}:
            raise ValueError("resolution doit être 'resolved' ou 'rejected'")

        dispute.status = resolution
        dispute.admin_notes = admin_notes or f"Set to {resolution} by {admin_user_id}"
        self.db.commit()
        self.db.refresh(dispute)

        FinancialAuditLogger.log(
            action=f"dispute_{resolution}",
            user_id=admin_user_id,
            payment_id=dispute.transaction_id or dispute.payout_id or dispute.id,
            amount=Decimal("0"),
            currency="",
            provider="internal",
            status=resolution,
        )
        return dispute

    # ─── Payment methods ─────────────────────────────────────────────────────

    def list_payment_methods(self, user_id: str) -> list:
        from app.models.payment_method import PaymentMethod as PM
        return self.db.execute(
            select(PM)
            .where(PM.user_id == user_id)
            .order_by(PM.is_default.desc(), PM.created_at.desc())
        ).scalars().all()

    def add_payment_method(
        self,
        user_id: str,
        method_type: str,
        provider: str,
        phone_number: str,
        country_code: str,
        nickname: str | None = None,
        is_default: bool = False,
    ):
        from app.models.payment_method import PaymentMethod as PM
        if is_default:
            self.db.execute(
                PM.__table__.update().where(PM.user_id == user_id).values(is_default=False)
            )
        method = PM(
            id=_uuid(),
            user_id=user_id,
            method_type=method_type,
            provider=provider,
            phone_number=phone_number,
            country_code=country_code,
            nickname=nickname or f"{provider} · ...{phone_number[-4:]}",
            details=f"{provider} · {phone_number}",
            is_default=is_default,
        )
        self.db.add(method)
        self.db.commit()
        self.db.refresh(method)
        return method

    def delete_payment_method(self, method_id: str, user_id: str) -> None:
        from app.models.payment_method import PaymentMethod as PM
        method = self.db.execute(
            select(PM).where(PM.id == method_id, PM.user_id == user_id)
        ).scalars().one_or_none()
        if method is None:
            raise ValueError("Méthode de paiement introuvable")
        self.db.delete(method)
        self.db.commit()


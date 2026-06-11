from __future__ import annotations

from collections import defaultdict
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
from app.models.social_protection import SocialProtectionEvent
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


class SocialSplitConfigError(EscrowError):
    """Raised when a social-split fund (pension/health/smoothing/zaska) has a non-zero
    amount to credit but no system wallet user id is configured for it.

    This must hard-fail and abort the whole release: crediting only some of the
    split lines while silently dropping others would debit the escrow without
    crediting the corresponding funds, breaking the wallet == ledger invariant.
    """


# Identifies the current split model (8% ZASKA / 7% pension / 5% health / 2.5% smoothing /
# 77.5% tasker net), introduced 2026-06. Older "escrow_release" transactions created before
# this change carry no "split_model" key (or "type": "zaska_commission") and used a flat
# 15% ZASKA commission / 85% tasker net split — see LEGACY_SPLIT_MODEL.
SOCIAL_SPLIT_MODEL = "social_v2"
LEGACY_SPLIT_MODEL = "legacy_v1"

SOCIAL_SPLIT_BPS: dict[str, int] = {
    "tasker_net": 7750,
    "zaska_operations": 800,
    "pension_fund": 700,
    "health_fund": 500,
    "smoothing_fund": 250,
}

SOCIAL_SPLIT_LINES: tuple[str, ...] = (
    "tasker_net",
    "zaska_operations",
    "pension_fund",
    "health_fund",
    "smoothing_fund",
)


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
        if norm in {"frozen_audit", "contested"}:
            return TransactionState.DISPUTED
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

    @staticmethod
    def calculate_social_split(amount: Decimal) -> dict[str, Decimal]:
        quant = Decimal("0.000001")
        tasker_amount = (amount * Decimal(SOCIAL_SPLIT_BPS["tasker_net"]) / Decimal("10000")).quantize(quant)
        zaska_amount = (amount * Decimal(SOCIAL_SPLIT_BPS["zaska_operations"]) / Decimal("10000")).quantize(quant)
        pension_amount = (amount * Decimal(SOCIAL_SPLIT_BPS["pension_fund"]) / Decimal("10000")).quantize(quant)
        health_amount = (amount * Decimal(SOCIAL_SPLIT_BPS["health_fund"]) / Decimal("10000")).quantize(quant)
        smoothing_amount = amount - tasker_amount - zaska_amount - pension_amount - health_amount
        return {
            "tasker_net": tasker_amount,
            "zaska_operations": zaska_amount,
            "pension_fund": pension_amount,
            "health_fund": health_amount,
            "smoothing_fund": smoothing_amount,
        }

    def _mirror_to_ledger(self, tx: Transaction, wallet: Wallet) -> None:
        """
        Mirror a just-created Transaction into the accounting ledger in real time,
        within the caller's own DB transaction (no extra commit). Lazy import
        avoids a circular import — accounting_ledger_service imports WalletService.
        """
        from app.services.accounting_ledger_service import AccountingLedgerService

        AccountingLedgerService(self.db).record_transaction_realtime(tx, wallet)

    @staticmethod
    def _parse_metadata(tx: Transaction | None) -> dict[str, Any]:
        if tx is None or not tx.metadata_json:
            return {}
        try:
            data = json.loads(tx.metadata_json)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _credit_social_split(self, escrow: Escrow, release_amount: Decimal, reference_prefix: str) -> tuple[Transaction, dict[str, Decimal]]:
        from app.core.config import settings as _cfg

        if not escrow.payee_id:
            raise EscrowError(f"Escrow {escrow.id} n'a pas de payee defini")

        split = self.calculate_social_split(release_amount)
        meta_base = {
            "escrow_id": escrow.id,
            "task_id": escrow.task_id,
            "gross": str(release_amount),
            "split_bps": SOCIAL_SPLIT_BPS,
            "type": "zaska_social_split",
            # Marks transactions produced by the post-2026-06 social split model
            # (8% ZASKA / pension / health / smoothing funds) so revenue reports can
            # tell them apart from the legacy 15%-commission model (split_model
            # absent or "legacy_v1") without silently dropping older data.
            "split_model": SOCIAL_SPLIT_MODEL,
        }

        fund_targets = {
            "zaska_operations": _cfg.zaska_wallet_user_id,
            "pension_fund": _cfg.pension_fund_user_id,
            "health_fund": _cfg.health_fund_user_id,
            "smoothing_fund": _cfg.smoothing_fund_user_id,
        }

        # Hard-fail BEFORE any wallet mutation: a fund with a non-zero share but no
        # configured system wallet would otherwise be debited from the escrow and
        # never credited anywhere, breaking the wallet == ledger invariant.
        missing = [
            split_line
            for split_line, user_id in fund_targets.items()
            if split[split_line] > Decimal("0") and not user_id
        ]
        if missing:
            raise SocialSplitConfigError(
                f"Escrow {escrow.id}: social split fund user id(s) not configured for "
                f"{', '.join(missing)} — refusing to release (would debit escrow without "
                f"crediting these funds)"
            )

        tasker_wallet = self._get_or_create_wallet(escrow.payee_id, escrow.currency, for_update=True, is_sandbox=escrow.is_sandbox)
        tasker_tx = Transaction(
            id=_uuid(),
            wallet_id=tasker_wallet.id,
            type="credit",
            amount=split["tasker_net"],
            status="completed",
            reference=f"{reference_prefix}:{escrow.id}:tasker",
            provider="internal",
            metadata_json=json.dumps({**meta_base, "split_line": "tasker_net"}),
            is_sandbox=escrow.is_sandbox,
        )
        tasker_wallet.balance += split["tasker_net"]
        self.db.add(tasker_tx)
        self.db.flush()
        self._mirror_to_ledger(tasker_tx, tasker_wallet)

        for split_line, user_id in fund_targets.items():
            amount = split[split_line]
            if amount <= Decimal("0"):
                continue
            fund_wallet = self._get_or_create_wallet(user_id, escrow.currency, for_update=True, is_sandbox=escrow.is_sandbox)
            fund_tx = Transaction(
                id=_uuid(),
                wallet_id=fund_wallet.id,
                type="credit",
                amount=amount,
                status="completed",
                reference=f"{reference_prefix}:{escrow.id}:{split_line}",
                provider="internal",
                metadata_json=json.dumps({**meta_base, "split_line": split_line}),
                is_sandbox=escrow.is_sandbox,
            )
            fund_wallet.balance += amount
            self.db.add(fund_tx)
            self._mirror_to_ledger(fund_tx, fund_wallet)

        return tasker_tx, split

    # ─── Wallet CRUD ────────────────────────────────────────────────────────

    def create_wallet(self, user_id: str, currency: str, *, is_sandbox: bool = False) -> Wallet:
        existing = (
            self.db.execute(
                select(Wallet).where(
                    Wallet.user_id == user_id,
                    Wallet.currency == currency,
                    Wallet.is_sandbox == is_sandbox,
                )
            )
            .scalars()
            .one_or_none()
        )
        if existing:
            return existing

        wallet = Wallet(id=_uuid(), user_id=user_id, currency=currency, balance=Decimal("0"), is_sandbox=is_sandbox)
        self.db.add(wallet)
        try:
            self.db.commit()
        except IntegrityError:
            # Concurrent creation: another request won the INSERT race, return the winner.
            self.db.rollback()
            return (
                self.db.execute(
                    select(Wallet).where(
                        Wallet.user_id == user_id,
                        Wallet.currency == currency,
                        Wallet.is_sandbox == is_sandbox,
                    )
                )
                .scalars()
                .one()
            )
        self.db.refresh(wallet)
        return wallet

    def get_wallet(self, user_id: str, currency: str, *, for_update: bool = False, is_sandbox: bool = False) -> Wallet:
        stmt = select(Wallet).where(
            Wallet.user_id == user_id,
            Wallet.currency == currency,
            Wallet.is_sandbox == is_sandbox,
        )
        if for_update:
            stmt = stmt.with_for_update()
        wallet = self.db.execute(stmt).scalars().one_or_none()
        if wallet is None:
            raise WalletNotFoundError(f"Wallet {currency} introuvable pour user {user_id}")
        return wallet

    def get_balance(self, user_id: str, currency: str, *, is_sandbox: bool = False) -> Decimal:
        return self.get_wallet(user_id, currency, is_sandbox=is_sandbox).balance

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
        *,
        is_sandbox: bool = False,
    ) -> Transaction:
        if amount <= Decimal("0"):
            raise ValueError("Le montant doit etre positif")

        # SELECT FOR UPDATE to prevent lost-update race on concurrent credits
        wallet = self._get_or_create_wallet(user_id, currency, for_update=True, is_sandbox=is_sandbox)

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
            is_sandbox=wallet.is_sandbox,
        )
        wallet.balance += amount
        self.db.add(tx)
        self._mirror_to_ledger(tx, wallet)
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
        *,
        is_sandbox: bool = False,
    ) -> Transaction:
        if amount <= Decimal("0"):
            raise ValueError("Le montant doit etre positif")

        wallet = self.get_wallet(user_id, currency, for_update=True, is_sandbox=is_sandbox)

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
            is_sandbox=wallet.is_sandbox,
        )
        wallet.balance -= amount
        self.db.add(tx)
        self._mirror_to_ledger(tx, wallet)
        self.db.commit()
        self.db.refresh(tx)
        return tx

    # ─── Escrow lifecycle ────────────────────────────────────────────────────

    def create_escrow(self, task_id: str, payer_id: str, payee_id: str | None, amount: Decimal, currency: str, *, is_sandbox: bool = False) -> Escrow:
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
        wallet = self.get_wallet(payer_id, currency, for_update=True, is_sandbox=is_sandbox)
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
            is_sandbox=is_sandbox,
        )
        wallet.balance -= amount
        self.db.add(tx)
        self.db.flush()  # assigns tx.id without committing
        self._mirror_to_ledger(tx, wallet)

        escrow = Escrow(
            id=escrow_id,
            task_id=task_id,
            payer_id=payer_id,
            payee_id=payee_id,
            amount=amount,
            currency=currency,
            status="funded",
            funding_tx_id=tx.id,
            is_sandbox=is_sandbox,
        )
        self.db.add(escrow)
        self.db.commit()  # single atomic commit — wallet debit + escrow creation
        self.db.refresh(escrow)
        return escrow

    def release_escrow(self, escrow_id: str, *, allow_frozen: bool = False) -> Escrow:
        escrow = self._get_escrow(escrow_id, for_update=True)
        # Accept "hold" too: scheduler auto-releases escrows in hold state after 6h window.
        # "frozen_audit"/"contested" escrows are under active dispute review — only the
        # dispute resolution flow (allow_frozen=True) may release them.
        allowed_statuses = {"funded", "hold"}
        if allow_frozen:
            allowed_statuses |= {"frozen_audit", "contested"}
        if escrow.status not in allowed_statuses:
            raise EscrowError(f"Escrow {escrow_id} ne peut etre libere (statut: {escrow.status})")
        if not escrow.payee_id:
            raise EscrowError(f"Escrow {escrow_id} n'a pas de payee defini")

        self._audit_transition(escrow, TransactionState.PROCESSING, "release_processing", "internal")

        tx, split = self._credit_social_split(escrow, escrow.amount, "escrow_release")
        escrow.status = "released"
        escrow.settlement_tx_id = tx.id
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
                    "split_bps": SOCIAL_SPLIT_BPS,
                    "split": {key: str(value) for key, value in split.items()},
                },
            )
        except Exception as _ledger_exc:
            logger.error(
                "AUDIT_TRAIL_FAILURE: EventLedger.log_financial failed for escrow=%s — %s",
                escrow_id, _ledger_exc,
            )
        self.db.commit()
        self.db.refresh(escrow)
        return escrow

    def refund_escrow(self, escrow_id: str, *, allow_frozen: bool = False) -> Escrow:
        escrow = self._get_escrow(escrow_id, for_update=True)
        # Accept "hold" too: escrow enters hold when tasker declares complete (6h window).
        # Admin cancel or tasker abandon during hold must still be refundable.
        # "frozen_audit"/"contested" escrows are under active dispute review — only the
        # dispute resolution flow (allow_frozen=True) may refund them.
        allowed_statuses = {"funded", "hold"}
        if allow_frozen:
            allowed_statuses |= {"frozen_audit", "contested"}
        if escrow.status not in allowed_statuses:
            raise EscrowError(f"Escrow {escrow_id} ne peut etre rembourse (statut: {escrow.status})")

        self._audit_transition(escrow, TransactionState.REFUNDED, "refund_processing", "internal")

        # Inline credit — single commit encompasses both wallet update and escrow status change.
        wallet = self._get_or_create_wallet(escrow.payer_id, escrow.currency, for_update=True, is_sandbox=escrow.is_sandbox)
        tx = Transaction(
            id=_uuid(),
            wallet_id=wallet.id,
            type="credit",
            amount=escrow.amount,
            status="completed",
            reference=f"escrow_refund:{escrow_id}",
            provider="internal",
            metadata_json=json.dumps({"escrow_id": escrow_id, "task_id": escrow.task_id}),
            is_sandbox=escrow.is_sandbox,
        )
        wallet.balance += escrow.amount
        self.db.add(tx)
        self.db.flush()  # obtain tx.id before commit
        self._mirror_to_ledger(tx, wallet)

        escrow.status = "refunded"
        escrow.settlement_tx_id = tx.id
        self.db.commit()  # single atomic commit
        self.db.refresh(escrow)
        return escrow

    def create_pending_escrow(self, task_id: str, payer_id: str, payee_id: str | None, amount: Decimal, currency: str, *, is_sandbox: bool = False) -> Escrow:
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
            is_sandbox=is_sandbox,
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

    def hold_escrow_for_minutes(self, escrow_id: str, minutes: int = 180) -> Escrow:
        """Transition funded to hold and start the client validation window."""
        from datetime import timedelta
        escrow = self._get_escrow(escrow_id, for_update=True)
        if escrow.status != "funded":
            raise EscrowError(f"Escrow {escrow_id} ne peut passer en hold (statut: {escrow.status})")
        escrow.status = "hold"
        escrow.payout_available_at = datetime.utcnow() + timedelta(minutes=minutes)
        self.db.commit()
        self.db.refresh(escrow)
        return escrow

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
        return self.freeze_escrow_for_audit(escrow_id, client_user_id)

    def freeze_escrow_for_audit(self, escrow_id: str, actor_user_id: str, *, commit: bool = True) -> Escrow:
        now = datetime.utcnow()
        escrow = self._get_escrow(escrow_id, for_update=True)
        if actor_user_id not in {escrow.payer_id, escrow.payee_id}:
            raise EscrowError("Seules les parties de la transaction peuvent geler cet escrow")
        if escrow.status not in {"funded", "hold", "contested"}:
            raise EscrowError(f"Escrow {escrow_id} ne peut pas être gelé pour audit (statut: {escrow.status})")
        escrow.status = "frozen_audit"
        escrow.contested_at = now
        if commit:
            self.db.commit()
            self.db.refresh(escrow)
        else:
            self.db.flush()
        return escrow

    def release_held_escrow(self, escrow_id: str) -> Escrow:
        """Release escrow after 24h hold has passed (no contest).

        P0-005 FIX: Do NOT call self.release_escrow() here — that would issue a second
        SELECT FOR UPDATE on the same row in the same transaction, which is wasteful and
        potentially inconsistent (release_escrow would re-read the row, possibly getting
        a cached/stale SQLAlchemy identity map entry).

        Instead, inline the release logic directly on the already-locked escrow.
        """
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

        tx, split = self._credit_social_split(escrow, escrow.amount, "escrow_auto_release")
        escrow.status = "released"
        escrow.settlement_tx_id = tx.id
        self.db.commit()
        self.db.refresh(escrow)
        FinancialAuditLogger.log(
            action="release_held_escrow",
            user_id=escrow.payee_id or "",
            payment_id=escrow.id,
            transaction_id=tx.id,
            amount=escrow.amount,
            currency=escrow.currency,
            provider="internal",
            status=escrow.status,
            state_before=TransactionState.PROCESSING.value,
            state_after=TransactionState.SUCCESS.value,
        )
        logger.info(
            "escrow_auto_released escrow={} split={}",
            escrow.id,
            {key: str(value) for key, value in split.items()},
        )
        return escrow

    def partial_release_escrow(
        self, escrow_id: str, completion_percent: int, *, allow_frozen: bool = False
    ) -> tuple[Escrow, Decimal, Decimal]:
        """Releases `completion_percent`% of the escrow gross to the tasker (via the
        social split) and refunds the remainder to the client.

        "frozen_audit"/"contested" escrows are under active dispute review — only the
        dispute resolution flow (allow_frozen=True) may partially release them.

        Returns (escrow, tasker_net_amount, client_refund).
        """
        escrow = self._get_escrow(escrow_id, for_update=True)
        allowed_statuses = {"funded", "hold"}
        if allow_frozen:
            allowed_statuses |= {"frozen_audit", "contested"}
        if escrow.status not in allowed_statuses:
            raise EscrowError(f"Escrow {escrow_id} ne peut être libéré partiellement (statut: {escrow.status})")
        if not escrow.payee_id:
            raise EscrowError(f"Escrow {escrow_id} n'a pas d'exécutant défini")

        release_amount = (escrow.amount * Decimal(str(completion_percent)) / Decimal("100")).quantize(Decimal("0.000001"))
        client_refund = escrow.amount - release_amount
        exec_tx, split = self._credit_social_split(escrow, release_amount, "partial_release")

        if client_refund > Decimal("0"):
            payer_wallet = self._get_or_create_wallet(escrow.payer_id, escrow.currency, for_update=True)
            refund_tx = Transaction(
                id=_uuid(),
                wallet_id=payer_wallet.id,
                type="credit",
                amount=client_refund,
                status="completed",
                reference=f"partial_refund:{escrow_id}",
                provider="internal",
                metadata_json=json.dumps({
                    "type": "partial_refund",
                    "escrow_id": escrow_id,
                    "task_id": escrow.task_id,
                    "completion_percent": completion_percent,
                    "released_gross": str(release_amount),
                }),
            )
            payer_wallet.balance += client_refund
            self.db.add(refund_tx)
            self._mirror_to_ledger(refund_tx, payer_wallet)

        escrow.status = "partial_released"
        escrow.settlement_tx_id = exec_tx.id
        self.db.commit()
        self.db.refresh(escrow)

        FinancialAuditLogger.log(
            action="partial_release_escrow",
            user_id=escrow.payee_id,
            payment_id=escrow.id,
            transaction_id=exec_tx.id,
            amount=release_amount,
            currency=escrow.currency,
            provider="internal",
            status=escrow.status,
        )
        return escrow, split["tasker_net"], client_refund

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

    def list_split_history(
        self,
        user_id: str,
        currency: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        base_txs = self._list_tasker_split_transactions(user_id=user_id, currency=currency)
        page = base_txs[offset: offset + limit]
        return [self._build_split_history_entry(tx) for tx in page]

    def get_social_protection_overview(self, user_id: str) -> dict[str, Any]:
        base_txs = self._list_tasker_split_transactions(user_id=user_id, currency=None)
        split_entries = [self._build_split_history_entry(tx) for tx in base_txs]
        social_events = self._list_social_protection_events(user_id=user_id)
        wallets = self.list_wallets(user_id)
        balances = [{"currency": wallet.currency, "balance": str(wallet.balance)} for wallet in wallets]

        if not split_entries:
            return {
                "balances": balances,
                "total_completed_tasks": 0,
                "first_task_at": None,
                "active_months": 0,
                "badge": self._compute_tasker_badge(0),
                "currencies": [],
            }

        first_task_at = min(entry["released_at"] for entry in split_entries if entry["released_at"])
        active_month_keys = {
            entry["released_at"][:7]
            for entry in split_entries
            if entry.get("released_at")
        }
        active_months = len(active_month_keys)
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for entry in split_entries:
            grouped[entry["currency"]].append(entry)
        events_by_currency: dict[str, list[SocialProtectionEvent]] = defaultdict(list)
        for event in social_events:
            events_by_currency[event.currency].append(event)

        now = datetime.utcnow()
        currency_summaries: list[dict[str, Any]] = []
        for currency_code, entries in grouped.items():
            currency_events = events_by_currency.get(currency_code, [])
            pension_total = sum(Decimal(entry["split"]["pension_fund"]) for entry in entries)
            health_total = sum(Decimal(entry["split"]["health_fund"]) for entry in entries)
            smoothing_total = sum(Decimal(entry["split"]["smoothing_fund"]) for entry in entries)
            first_currency_task = min(entry["released_at"] for entry in entries if entry["released_at"])
            elapsed_days = max(1, (now - datetime.fromisoformat(first_currency_task)).days) if first_currency_task else 1
            elapsed_years = Decimal(str(elapsed_days)) / Decimal("365")
            pension_interest = (pension_total * Decimal("0.06") * elapsed_years).quantize(Decimal("0.000001"))
            smoothing_interest = (smoothing_total * Decimal("0.04") * elapsed_years).quantize(Decimal("0.000001"))
            monthly_pension_run_rate = (
                ((pension_total / Decimal(str(max(active_months, 1)))) * Decimal("5") * Decimal("1.06")) / Decimal("240")
            ).quantize(Decimal("0.000001"))

            current_month = now.strftime("%Y-%m")
            has_health_this_month = any(
                entry["released_at"].startswith(current_month) and Decimal(entry["split"]["health_fund"]) > Decimal("0")
                for entry in entries
                if entry.get("released_at")
            )
            smoothing_intervention_total = sum(
                event.amount for event in currency_events if event.event_type == "SMOOTHING_INTERVENTION"
            )
            smoothing_reimbursement_total = sum(
                event.amount for event in currency_events if event.event_type == "SMOOTHING_REIMBURSEMENT"
            )
            has_smoothing_maintenance_this_month = any(
                event.event_type == "SMOOTHING_INTERVENTION" and event.period_key == current_month
                for event in currency_events
            )
            coverage_days = now.day if (has_health_this_month or has_smoothing_maintenance_this_month) else 0
            health_activation_date = min(
                (entry["released_at"] for entry in entries if Decimal(entry["split"]["health_fund"]) > Decimal("0")),
                default=None,
            )
            intervention_dates = [
                event.created_at.isoformat()
                for event in currency_events
                if event.event_type == "SMOOTHING_INTERVENTION"
            ]
            if not health_activation_date and intervention_dates:
                health_activation_date = min(intervention_dates)
            smoothing_available_balance = max(
                Decimal("0"),
                smoothing_total - smoothing_intervention_total + smoothing_reimbursement_total,
            )
            intervention_history = [
                {
                    "type": event.event_type,
                    "amount": str(event.amount),
                    "period_key": event.period_key,
                    "created_at": event.created_at.isoformat(),
                    "status": event.status,
                }
                for event in currency_events
                if event.event_type == "SMOOTHING_INTERVENTION"
            ]

            currency_summaries.append(
                {
                    "currency": currency_code,
                    "pension": {
                        "total_contributed": str(pension_total),
                        "simulated_interest": str(pension_interest),
                        "projected_monthly_pension": str(monthly_pension_run_rate),
                        "projection_basis": "run_rate_simulation",
                        "progress_percent_to_guarantee": round(min(100, (active_months / 60) * 100), 2),
                    },
                    "health": {
                        "status": "ACTIVE" if (has_health_this_month or has_smoothing_maintenance_this_month) else "INACTIVE",
                        "activation_date": health_activation_date,
                        "active_days_this_month": coverage_days,
                        "total_paid_to_authorities": str(health_total),
                        "maintained_by_smoothing_this_month": has_smoothing_maintenance_this_month,
                    },
                    "smoothing": {
                        "available_balance": str(smoothing_available_balance),
                        "total_contributed": str(smoothing_total),
                        "interest_redirected_to_pension": str(smoothing_interest),
                        "interventions": intervention_history,
                        "outstanding_reconstitution": str(
                            max(Decimal("0"), smoothing_intervention_total - smoothing_reimbursement_total)
                        ),
                    },
                }
            )

        return {
            "balances": balances,
            "total_completed_tasks": len(split_entries),
            "first_task_at": first_task_at,
            "active_months": active_months,
            "badge": self._compute_tasker_badge(active_months),
            "currencies": currency_summaries,
        }

    def _list_tasker_split_transactions(self, user_id: str, currency: str | None = None) -> list[Transaction]:
        wallets = self.list_wallets(user_id)
        if currency:
            wallets = [wallet for wallet in wallets if wallet.currency == currency.upper()]
        wallet_ids = [wallet.id for wallet in wallets]
        if not wallet_ids:
            return []
        txs = (
            self.db.execute(
                select(Transaction)
                .where(
                    Transaction.wallet_id.in_(wallet_ids),
                    Transaction.type == "credit",
                    Transaction.status == "completed",
                )
                .order_by(Transaction.created_at.desc())
            )
            .scalars()
            .all()
        )
        result: list[Transaction] = []
        for tx in txs:
            metadata = self._parse_metadata(tx)
            split_line = metadata.get("split_line")
            if split_line == "tasker_net":
                result.append(tx)
                continue
            if tx.reference.endswith(":tasker") and metadata.get("type") == "zaska_social_split":
                result.append(tx)
        return result

    def _build_split_history_entry(self, tx: Transaction) -> dict[str, Any]:
        metadata = self._parse_metadata(tx)
        gross = Decimal(str(metadata.get("gross", "0") or "0"))
        task_id = metadata.get("task_id")
        escrow_id = metadata.get("escrow_id")
        reference_prefix = tx.reference.rsplit(":", 1)[0]
        line_refs = {line: f"{reference_prefix}:{line}" for line in SOCIAL_SPLIT_LINES if line != "tasker_net"}
        companion_txs = (
            self.db.execute(select(Transaction).where(Transaction.reference.in_(list(line_refs.values()))))
            .scalars()
            .all()
        )
        companion_by_ref = {item.reference: item for item in companion_txs}

        split: dict[str, Decimal] = {"tasker_net": tx.amount}
        for line, ref in line_refs.items():
            split[line] = companion_by_ref.get(ref).amount if companion_by_ref.get(ref) else Decimal("0")
        if gross <= Decimal("0"):
            gross = sum(split.values())
        elif split["tasker_net"] <= Decimal("0"):
            split = self.calculate_social_split(gross)

        task_title = None
        if task_id:
            from app.models.task import Task

            task = self.db.execute(select(Task).where(Task.id == task_id)).scalars().one_or_none()
            task_title = task.title if task else None

        return {
            "transaction_id": tx.id,
            "task_id": task_id,
            "task_title": task_title,
            "escrow_id": escrow_id,
            "currency": self._currency_for_wallet_id(tx.wallet_id),
            "gross_amount": str(gross),
            "released_at": tx.created_at.isoformat(),
            "split": {line: str(amount) for line, amount in split.items()},
            "reference": tx.reference,
        }

    def _currency_for_wallet_id(self, wallet_id: str) -> str:
        wallet = self.db.execute(select(Wallet).where(Wallet.id == wallet_id)).scalars().one()
        return wallet.currency

    def _list_social_protection_events(
        self,
        user_id: str,
        currency: str | None = None,
    ) -> list[SocialProtectionEvent]:
        stmt = select(SocialProtectionEvent).where(SocialProtectionEvent.user_id == user_id)
        if currency:
            stmt = stmt.where(SocialProtectionEvent.currency == currency.upper())
        return self.db.execute(stmt.order_by(SocialProtectionEvent.created_at.desc())).scalars().all()

    @staticmethod
    def _compute_tasker_badge(active_months: int) -> dict[str, Any]:
        if active_months < 3:
            return {"code": "NEW_TASKER", "label": "Nouveau Tasker", "description": "0 à 3 mois d'activité"}
        if active_months < 12:
            return {"code": "ACTIVE_TASKER", "label": "Tasker Actif", "description": "3 à 12 mois d'activité"}
        if active_months < 36:
            return {"code": "CONFIRMED_TASKER", "label": "Tasker Confirmé", "description": "1 à 3 ans d'activité"}
        if active_months < 60:
            return {"code": "SENIOR_TASKER", "label": "Tasker Senior", "description": "3 à 5 ans d'activité"}
        return {"code": "PROTECTED_TASKER", "label": "Tasker Protégé", "description": "5 ans et plus, garantie activée"}

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
        self._mirror_to_ledger(debit_tx, from_wallet)

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
        self._mirror_to_ledger(credit_tx, to_wallet)

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

    def _get_or_create_wallet(self, user_id: str, currency: str, *, for_update: bool = False, is_sandbox: bool = False) -> Wallet:
        stmt = select(Wallet).where(
            Wallet.user_id == user_id,
            Wallet.currency == currency,
            Wallet.is_sandbox == is_sandbox,
        )
        if for_update:
            stmt = stmt.with_for_update()
        wallet = self.db.execute(stmt).scalars().one_or_none()
        if wallet is None:
            new_wallet = Wallet(id=_uuid(), user_id=user_id, currency=currency, balance=Decimal("0"), is_sandbox=is_sandbox)
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
                    select(Wallet).where(
                        Wallet.user_id == user_id,
                        Wallet.currency == currency,
                        Wallet.is_sandbox == is_sandbox,
                    )
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

        existing_debit = self.db.execute(
            select(Transaction)
            .join(Wallet, Wallet.id == Transaction.wallet_id)
            .where(
                Wallet.user_id == from_user_id,
                Wallet.currency == currency,
                Transaction.reference == f"transfer_out:{reference}",
                Transaction.type == "debit",
            )
        ).scalars().one_or_none()
        existing_credit = self.db.execute(
            select(Transaction)
            .join(Wallet, Wallet.id == Transaction.wallet_id)
            .where(
                Wallet.user_id == to_user_id,
                Wallet.currency == currency,
                Transaction.reference == f"transfer_in:{reference}",
                Transaction.type == "credit",
            )
        ).scalars().one_or_none()
        if existing_debit is not None and existing_credit is not None:
            return existing_debit, existing_credit

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
        self._mirror_to_ledger(debit_tx, from_wallet)
        self._mirror_to_ledger(credit_tx, to_wallet)
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
        self._mirror_to_ledger(rev_tx, wallet)

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


"""
ReconciliationEngine — compares local ledger with provider records.

Two reconciliation passes:
  1. Escrow pass  — checks locally-pending escrows against inbound transactions
  2. Payout pass  — polls FedaPay/Flutterwave for the live status of processing payouts

Results are stored in `reconciliation_reports` and emitted to the audit log.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.observability import logger
from app.core.payments.transaction_state_machine import TransactionState
from app.models.dispute import ReconciliationReport
from app.models.payout import Payout
from app.models.wallet import Escrow, Transaction
from app.payment.audit_logger import FinancialAuditLogger
from app.services.wallet_service import WalletService


def _uuid() -> str:
    return str(uuid.uuid4())


class ReconciliationEngine:
    def __init__(self, db: Session):
        self.db = db

    # ── Public entry point ────────────────────────────────────────────────────

    def reconcile_all(self, country_code: str) -> dict:
        report: dict = {
            "country_code": country_code,
            "run_at": datetime.utcnow().isoformat(),
            "mismatches": [],
            "repaired": 0,
            "payout_updates": [],
        }

        self._reconcile_escrows(report)
        self._reconcile_payouts(report)

        matched = len([m for m in report["mismatches"] if m.get("repaired")])
        self._save_report(
            country_code=country_code,
            matched_count=matched,
            missing_count=len([m for m in report["mismatches"] if m.get("type") == "paid_in_provider_not_db"]),
            inconsistent_count=len([m for m in report["mismatches"] if m.get("type") in {
                "duplicate_payments", "failed_in_db_but_success_provider"
            }]),
            repaired_count=report["repaired"],
            report_json=json.dumps(report),
        )
        return report

    # ── Escrow reconciliation ─────────────────────────────────────────────────

    def _reconcile_escrows(self, report: dict) -> None:
        escrows = self.db.execute(select(Escrow)).scalars().all()
        txs = self.db.execute(select(Transaction)).scalars().all()

        inbound_by_escrow: dict[str, list[Transaction]] = {}
        for tx in txs:
            if tx.reference.startswith("pay:") and tx.metadata_json:
                try:
                    meta = json.loads(tx.metadata_json)
                    eid = meta.get("escrow_id")
                    if eid:
                        inbound_by_escrow.setdefault(eid, []).append(tx)
                except Exception:
                    pass

        wallet = WalletService(self.db)
        for esc in escrows:
            provider_txs = inbound_by_escrow.get(esc.id, [])
            if provider_txs and esc.status == "pending":
                report["mismatches"].append({
                    "type": "paid_in_provider_not_db",
                    "escrow_id": esc.id,
                    "repaired": True,
                })
                self._mark_as_success(wallet, esc.id, provider_txs[0].provider, provider_txs[0].reference)
                report["repaired"] += 1
            if len(provider_txs) > 1:
                report["mismatches"].append({
                    "type": "duplicate_payments",
                    "escrow_id": esc.id,
                    "repaired": False,
                })
                self._flag_for_manual_review(esc.id, report["country_code"])
            if provider_txs and esc.status == "cancelled":
                report["mismatches"].append({
                    "type": "failed_in_db_but_success_provider",
                    "escrow_id": esc.id,
                    "repaired": False,
                })
                self._flag_for_manual_review(esc.id, report["country_code"])

    # ── Payout reconciliation ─────────────────────────────────────────────────

    def _reconcile_payouts(self, report: dict) -> None:
        """
        Find payouts stuck in 'processing' for > STALE_MINUTES and poll the provider.
        Updates payout status + re-credits wallet on confirmed failure.
        """
        stale_cutoff = datetime.utcnow() - timedelta(
            minutes=settings.payout_monitor_stale_minutes
        )
        stale_payouts = (
            self.db.execute(
                select(Payout).where(
                    Payout.status.in_(["processing", "pending"]),
                    Payout.created_at < stale_cutoff,
                )
            )
            .scalars()
            .all()
        )

        wallet_svc = WalletService(self.db)
        for payout in stale_payouts:
            if not payout.provider_tx_id:
                continue
            try:
                live_status = self._fetch_provider_payout_status(payout)
            except Exception as exc:
                logger.warning(
                    "recon:payout_status_fetch_failed payout_id={} provider={} error={}",
                    payout.id, payout.provider, exc,
                )
                continue

            if live_status == payout.status:
                continue

            payout.status = live_status
            if live_status == "failed":
                payout.failure_reason = "reconciliation: provider confirmed failure"
                self.db.commit()
                self._rollback_payout(wallet_svc, payout)
            else:
                self.db.commit()

            report["payout_updates"].append({
                "payout_id": payout.id,
                "provider": payout.provider,
                "new_status": live_status,
            })
            FinancialAuditLogger.log(
                action="recon:payout_status_updated",
                user_id=payout.user_id,
                payment_id=payout.provider_tx_id or payout.id,
                amount=payout.amount,
                currency=payout.currency,
                provider=payout.provider,
                status=live_status,
            )

    def _fetch_provider_payout_status(self, payout: Payout) -> str:
        """Synchronous HTTP call to provider. Returns 'completed' | 'pending' | 'failed'."""
        provider = payout.provider.lower()
        tx_id = payout.provider_tx_id

        if provider == "flutterwave":
            return self._flutterwave_transfer_status(tx_id)
        if provider == "fedapay":
            return self._fedapay_payout_status(tx_id)
        # Unknown provider — leave as-is
        return payout.status

    def _flutterwave_transfer_status(self, transfer_id: str) -> str:
        headers = {
            "Authorization": f"Bearer {settings.flutterwave_secret_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(
                f"https://api.flutterwave.com/v3/transfers/{transfer_id}",
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        status_str = str(data.get("data", {}).get("status", "PENDING")).upper()
        if status_str == "SUCCESSFUL":
            return "completed"
        if status_str in ("FAILED", "CANCELLED"):
            return "failed"
        return "pending"

    def _fedapay_payout_status(self, payout_id: str) -> str:
        base = (
            "https://api.fedapay.com/v1"
            if settings.fedapay_env == "live"
            else "https://sandbox-api.fedapay.com/v1"
        )
        headers = {
            "Authorization": f"Bearer {settings.fedapay_api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(f"{base}/payouts/{payout_id}", headers=headers)
            resp.raise_for_status()
            data = resp.json()

        status_str = str(
            data.get("v_payout", data).get("status", "pending")
        ).lower()
        if status_str in ("sent", "approved"):
            return "completed"
        if status_str in ("failed", "cancelled", "declined"):
            return "failed"
        return "pending"

    def _rollback_payout(self, wallet_svc: WalletService, payout: Payout) -> None:
        """Re-credit wallet when reconciliation confirms a payout failed."""
        try:
            wallet_svc.credit_wallet(
                user_id=payout.user_id,
                currency=payout.currency,
                amount=payout.amount,
                reference=f"recon_rollback:{payout.id}",
                provider="internal",
                metadata={
                    "type": "payout_recon_rollback",
                    "payout_id": payout.id,
                    "provider": payout.provider,
                },
            )
            logger.info(
                "recon:payout_rolled_back payout_id={} user={} amount={} {}",
                payout.id, payout.user_id, payout.amount, payout.currency,
            )
        except Exception as exc:
            logger.error(
                "recon:payout_rollback_failed CRITICAL payout_id={} error={}",
                payout.id, exc,
            )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _mark_as_success(
        self, wallet: WalletService, escrow_id: str, provider: str, provider_tx_id: str
    ) -> None:
        esc = wallet._get_escrow(escrow_id)
        if esc.status == "pending":
            wallet.fund_escrow_from_payment(escrow_id, provider, provider_tx_id)

    def _flag_for_manual_review(self, escrow_id: str, country_code: str) -> None:
        esc = self.db.execute(
            select(Escrow).where(Escrow.id == escrow_id)
        ).scalars().one_or_none()
        if not esc:
            return
        FinancialAuditLogger.log(
            action="manual_review_required",
            user_id=esc.payer_id,
            payment_id=esc.id,
            transaction_id=esc.id,
            amount=esc.amount,
            currency=esc.currency,
            provider="internal",
            status=TransactionState.RECONCILING.value.lower(),
            state_before=esc.status.upper(),
            state_after=TransactionState.RECONCILING.value,
            country_code=country_code,
        )

    def _save_report(
        self,
        country_code: str,
        matched_count: int,
        missing_count: int,
        inconsistent_count: int,
        repaired_count: int,
        report_json: str,
    ) -> ReconciliationReport:
        record = ReconciliationReport(
            id=_uuid(),
            run_at=datetime.utcnow(),
            country_code=country_code,
            matched_count=matched_count,
            missing_count=missing_count,
            inconsistent_count=inconsistent_count,
            repaired_count=repaired_count,
            report_json=report_json,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        logger.info(
            "recon:report_saved id={} matched={} missing={} inconsistent={} repaired={}",
            record.id, matched_count, missing_count, inconsistent_count, repaired_count,
        )
        return record

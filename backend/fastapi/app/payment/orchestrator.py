"""
PaymentOrchestrator — Global Payment Orchestration System (Africa-first, world-ready).

Architecture:
  API Route
    → PaymentOrchestrator.execute(intent)
        1. SafetyLayer.assert_create_payment_safe()   — user verified, currency OK
        2. TransactionLimits checks                   — daily/fraud limits (Redis Lua)
        3. PaymentRouterService.route_payment()        — routing rules (country → provider)
        4. IdempotencyService.lock()                  — Redis lock (NX + TTL)
        5. WalletService.create_pending_escrow()      — ledger entry (pending)
        6. ProviderRouter.execute_with_fallback()     — call primary, fallback on error
        7. FinancialAuditLogger.log()                 — immutable audit trail
    ← OrchestratorResult

Routing rules:
  Africa CFA zone (TG, BJ, CI, SN…) → FedaPay (Mobile Money XOF)
  Ghana                               → Flutterwave (MTN MoMo GHS)
  Nigeria + sub-saharan               → Flutterwave (card/mobile)
  EU                                  → Stripe (card, Apple Pay, Google Pay)
  US / International                  → Stripe (card)
  Dev / no real money                 → MockProvider

Safety guarantees:
  - Idempotent: same key always returns the same result (no double escrow)
  - Atomic: pending escrow creation + provider call inside Redis lock
  - Audited: every attempt logged to FinancialAuditLog (immutable)
  - Fallback: dev/mock mode automatically if real provider unavailable in dev
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.country_engine import PaymentRouterService
from app.core.country_engine.definitions import get_config
from app.core.fx_rate import get_live_fx_rate
from app.core.observability import logger
from app.models.task import Task
from app.models.user import User
from app.payment.audit_logger import FinancialAuditLogger
from app.payment.idempotency import IdempotencyError, IdempotencyService
from app.payment.limits import FraudDetected, LimitExceeded, TransactionLimits
from app.payment.providers import get_payment_provider
from app.payment.safety_layer import PaymentSafetyError, PaymentSafetyLayer
from app.services.payment import PaymentProviderError, UnsupportedCountryError
from app.services.wallet_service import WalletService


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class OrchestratorResult:
    mode: str                           # mock | sandbox | production
    real_money_enabled: bool
    provider: str                       # stripe | fedapay | flutterwave | mock
    provider_intent_id: str
    client_secret: str | None           # Stripe Elements
    payment_url: str | None             # FedaPay / Flutterwave redirect
    escrow_id: str
    amount: Decimal
    currency: str
    commission: float
    escrow_amount: float
    idempotency_key: str
    region: str                         # EU | WAF_CFA | WAF | INTL
    raw: dict[str, Any] = field(default_factory=dict)


# ── Errors ────────────────────────────────────────────────────────────────────

class OrchestratorError(Exception):
    """Raised when the orchestrator cannot complete the payment."""
    http_status: int = 422

    def __init__(self, message: str, http_status: int = 422) -> None:
        super().__init__(message)
        self.http_status = http_status


# ── PaymentOrchestrator ───────────────────────────────────────────────────────

class PaymentOrchestrator:
    """
    Central payment orchestration service.

    One instance per request (holds a DB session). Stateless between requests.
    """

    def __init__(self, db: Session, wallet_svc: WalletService) -> None:
        self.db = db
        self.wallet_svc = wallet_svc
        self._safety = PaymentSafetyLayer(db)
        self._idem = IdempotencyService(ttl_seconds=settings.__dict__.get("payment_idempotency_ttl_seconds", 180))
        self._limits = TransactionLimits(fx_rate_usd_to_xof=get_live_fx_rate())

    # ── Public entry point ────────────────────────────────────────────────────

    async def execute(
        self,
        *,
        task_id: str,
        user_id: str,
        country_code: str,
        idempotency_key: str | None,
        real_money_override: bool | None = None,
    ) -> OrchestratorResult:
        """
        Orchestrate a payment intent for a task.

        Steps:
          1. Validate task
          2. Safety checks (user verified, currency, KYC gate)
          3. Fraud / limit checks
          4. Routing decision
          5. Idempotency lock
          6. Create pending escrow in ledger
          7. Call provider (with fallback)
          8. Audit log
          9. Return result
        """
        # ── Step 1: Load task ─────────────────────────────────────────────────
        task: Task | None = self.db.get(Task, task_id)
        if not task:
            raise OrchestratorError("Tâche introuvable", 404)

        amount = Decimal(str(task.price))
        currency = (task.currency or "XOF").upper()
        cc = country_code.upper()

        # ── Step 2: Safety checks ──────────────────────────────────────────────
        # Auto-generate idempotency key in dev/mock mode
        if not idempotency_key and settings.payment_mode in {"production", "sandbox"}:
            raise OrchestratorError("X-Idempotency-Key header is required in sandbox/production", 400)
        idem_key = idempotency_key or f"dev-{uuid.uuid4().hex}"

        try:
            safety_ctx = self._safety.assert_create_payment_safe(
                user_id=user_id,
                country_code=cc,
                amount=amount,
                currency=currency,
                idempotency_key=idem_key,
            )
        except PaymentSafetyError as exc:
            raise OrchestratorError(str(exc), 403) from exc

        # ── Step 3: Fraud / limit checks ──────────────────────────────────────
        try:
            self._limits.check_and_record_deposit_daily(
                user_id=user_id,
                amount=amount,
                currency=currency,
                max_usd=Decimal(str(settings.max_deposit_per_day_usd)),
            )
        except LimitExceeded as exc:
            raise OrchestratorError(str(exc), 429) from exc
        except FraudDetected as exc:
            raise OrchestratorError(str(exc), 403) from exc

        # ── Step 4: Routing decision ───────────────────────────────────────────
        route = PaymentRouterService.route_payment(cc, float(amount), currency)
        commission_info = PaymentRouterService.compute_commission(float(amount), cc)

        # Determine actual payment mode
        real_money = self._is_real_money_enabled(cc) if real_money_override is None else real_money_override
        effective_mode = "mock" if not real_money else settings.payment_mode

        # ── Step 5: Idempotency lock ───────────────────────────────────────────
        payload_fp = f"{user_id}|{amount}|{currency}|{cc}|{route.provider}"
        try:
            with self._idem.lock(idem_key, payload_fp):
                result = await self._execute_locked(
                    task=task,
                    user_id=user_id,
                    amount=amount,
                    currency=currency,
                    cc=cc,
                    route=route,
                    effective_mode=effective_mode,
                    idem_key=idem_key,
                    commission_info=commission_info,
                    safety_ctx=safety_ctx,
                )
        except IdempotencyError as exc:
            raise OrchestratorError(str(exc), 409) from exc

        return result

    # ── Internal: inside the idempotency lock ─────────────────────────────────

    async def _execute_locked(
        self,
        *,
        task: Task,
        user_id: str,
        amount: Decimal,
        currency: str,
        cc: str,
        route: Any,
        effective_mode: str,
        idem_key: str,
        commission_info: dict,
        safety_ctx: Any,
    ) -> OrchestratorResult:
        # ── Step 6: Create pending escrow (ledger entry) ───────────────────────
        escrow = self.wallet_svc.create_pending_escrow(
            task_id=task.id,
            payer_id=user_id,
            payee_id=task.assigned_to,
            amount=amount,
            currency=currency,
        )

        # ── Step 7: Call provider with fallback ────────────────────────────────
        user: User | None = self.db.get(User, user_id)
        user_email = (user.email if user else "") or ""

        provider_result = await self._call_provider_with_fallback(
            effective_mode=effective_mode,
            cc=cc,
            amount=amount,
            currency=currency,
            user_id=user_id,
            user_email=user_email,
            task=task,
            escrow_id=escrow.id,
            idem_key=idem_key,
            route=route,
        )

        # ── Step 8: Audit log ──────────────────────────────────────────────────
        FinancialAuditLogger.log(
            action="payment_intent_created",
            user_id=user_id,
            payment_id=provider_result["payment_id"],
            amount=amount,
            currency=currency,
            provider=provider_result["provider"],
            status="created",
            country_code=cc,
        )
        logger.info(
            "orchestrator:intent_created user={} escrow={} provider={} amount={} {}",
            user_id, escrow.id, provider_result["provider"], amount, currency,
        )

        return OrchestratorResult(
            mode=safety_ctx.payment_mode.value,
            real_money_enabled=(effective_mode != "mock"),
            provider=provider_result["provider"],
            provider_intent_id=provider_result["payment_id"],
            client_secret=provider_result.get("client_secret"),
            payment_url=provider_result.get("payment_url"),
            escrow_id=escrow.id,
            amount=amount,
            currency=currency,
            commission=commission_info["commission"],
            escrow_amount=commission_info["escrow_amount"],
            idempotency_key=idem_key,
            region=route.region,
            raw=provider_result,
        )

    async def _call_provider_with_fallback(
        self,
        *,
        effective_mode: str,
        cc: str,
        amount: Decimal,
        currency: str,
        user_id: str,
        user_email: str,
        task: Task,
        escrow_id: str,
        idem_key: str,
        route: Any,
    ) -> dict:
        """
        Call the canonical provider. All providers are interchangeable via the
        PaymentProvider interface — no business logic depends on a specific one.

        Mobile Money resilience: African routes (WAF_CFA/WAF) apply exponential
        backoff retry for transient telco failures before giving up.

        Fallback policy:
          - dev/mock mode: fall back to MockProvider on any provider error
          - sandbox/production: fail hard, no silent mock fallback
        """
        task_description = str(
            getattr(task, "description", None) or getattr(task, "title", None) or "Tâche ZASKA"
        )

        # Provider-agnostic: get_payment_provider returns a canonical PaymentProvider
        provider = get_payment_provider(payment_mode=effective_mode, country_code=cc)

        # Apply MM resilience wrapper for African mobile money routes under real conditions.
        # Low-bank-infrastructure: telco APIs are intermittent, confirmations are async.
        is_mm_route = route.method == "mobile_money" and route.region in {"WAF_CFA", "WAF"}

        async def _invoke():
            return await provider.create_payment_intent(
                amount=amount,
                currency=currency,
                user_id=user_id,
                user_email=user_email,
                escrow_id=escrow_id,
                task_id=task.id,
                task_description=task_description,
                country_code=cc,
                idempotency_key=idem_key,
            )

        try:
            if is_mm_route and effective_mode != "mock":
                from app.payment.mobile_money import retry_mm_call
                result = await retry_mm_call(
                    _invoke,
                    operation_name=f"create_intent:{route.provider}",
                )
            else:
                result = await _invoke()

            if effective_mode != "mock":
                self._safety.assert_provider_mode_keys(route.provider)

            return {
                "provider": result.provider,
                "payment_id": result.provider_intent_id,
                "client_secret": result.client_secret,
                "payment_url": result.payment_url,
            }
        except (PaymentProviderError, UnsupportedCountryError, NotImplementedError) as exc:
            if effective_mode == "mock":
                raise OrchestratorError(f"Mock provider error: {exc}", 502) from exc

            if settings.payment_mode in {"dev", "mock"}:
                logger.warning(
                    "orchestrator:provider_fallback provider={} country={} error={} — falling back to mock",
                    route.provider, cc, exc,
                )
                from app.services.payment.mock_provider import MockProvider
                mock = MockProvider()
                fallback = await mock.create_payment_intent(
                    amount=amount,
                    currency=currency,
                    user_id=user_id,
                    user_email=user_email,
                    escrow_id=escrow_id,
                    task_id=task.id,
                    task_description=task_description,
                    country_code=cc,
                    idempotency_key=idem_key,
                )
                return {
                    "provider": "mock_fallback",
                    "payment_id": fallback.provider_intent_id,
                    "client_secret": fallback.client_secret,
                    "payment_url": fallback.payment_url,
                }
            # sandbox/production: fail hard — no silent fallback to mock
            raise OrchestratorError(f"Erreur provider {route.provider}: {exc}", 502) from exc

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _is_real_money_enabled(self, country_code: str) -> bool:
        if not settings.real_money_enabled:
            return False
        try:
            from app.core.country_engine.feature_engine import FeatureFlagEngine
            from app.core.redis_client import redis_sync
            return FeatureFlagEngine(redis_sync, self.db).get_flag(country_code, "real_money_enabled")
        except Exception:
            return False

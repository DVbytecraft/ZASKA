"""
Wallet API - ZASKA PAY endpoints.

Toutes les routes requierent un JWT valide (get_current_user_id).
Aucun provider de paiement n'est appele directement ici.
"""

from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse, urlunparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.api.deps import (
    get_async_wallet_service,
    get_country_code,
    get_current_user_id,
    get_wallet_service,
    require_admin,
    require_kyc_approved,
    require_kyc_not_rejected,
)
from app.core.config import settings
from app.core.fx_rate import get_live_fx_rate
from app.core.observability import logger
from app.core.redis_client import redis_sync
from app.core.responses import success_response
from app.models.user import User
from app.payment.audit_logger import FinancialAuditLogger
from app.payment.limits import FraudDetected, LimitExceeded, TransactionLimits
from app.payment.safety_layer import PaymentSafetyError, PaymentSafetyLayer
from app.services.payment.base_provider import PaymentProviderError
from app.services.payment.mobile_money_topup import (
    create_mobile_money_topup,
    execute_mobile_money_payout,
)
from app.services.wallet_service import (
    AsyncWalletService,
    EscrowError,
    InsufficientFundsError,
    PayoutCreationFailedException,
    WalletNotFoundError,
    WalletService,
)

try:
    import stripe as _stripe  # stripe==11.4.0 dans requirements.txt
except ImportError:  # pragma: no cover — stripe toujours présent en prod
    _stripe = None  # type: ignore[assignment]

router = APIRouter(prefix="/wallet", tags=["wallet"])


def _wallet_frontend_url(path: str) -> str:
    """Derive the frontend origin from PAYMENT_REDIRECT_URL and append path."""
    try:
        parsed = urlparse(settings.payment_redirect_url)
        return urlunparse(parsed._replace(path=path, query="", fragment=""))
    except Exception:
        return f"http://localhost:3010{path}"


def _wallet_rate_limit(user_id: str) -> None:
    # P1-007 FIX: Send INCR + EXPIRE in a single pipeline round-trip.
    # Old code: two separate calls — if the process crashed after INCR but before
    # EXPIRE, the key never expired and the user was permanently rate-limited.
    # With a pipeline both commands land on Redis atomically (same network frame),
    # eliminating the crash window between them.
    key = f"rl:wallet:{user_id}"
    pipe = redis_sync.pipeline(transaction=False)
    pipe.incr(key)
    pipe.expire(key, 60)
    n = pipe.execute()[0]
    if n > 60:
        raise HTTPException(status_code=429, detail="Too many wallet requests")


def _assert_payments_enabled() -> None:
    if settings.payments_disabled:
        raise HTTPException(status_code=503, detail="Payments are globally disabled")


class WalletCreatePayload(BaseModel):
    currency: str

    @field_validator("currency")
    @classmethod
    def upper(cls, v: str) -> str:
        return v.upper()


class CreditPayload(BaseModel):
    target_user_id: str          # user to credit — admin specifies explicitly
    currency: str
    amount: str
    reference: str
    provider: str = "internal"

    @field_validator("currency")
    @classmethod
    def upper_currency(cls, v: str) -> str:
        return v.upper()

    def decimal_amount(self) -> Decimal:
        try:
            v = Decimal(self.amount)
            if v <= Decimal("0"):
                raise ValueError
            return v
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Montant invalide") from exc


class EscrowCreatePayload(BaseModel):
    task_id: str
    payee_id: str | None = None
    amount: str
    currency: str

    def decimal_amount(self) -> Decimal:
        try:
            return Decimal(self.amount)
        except InvalidOperation as exc:
            raise ValueError("Montant invalide") from exc


@router.post("/create")
def create_wallet(
    payload: WalletCreatePayload,
    user_id: str = Depends(get_current_user_id),
    svc: WalletService = Depends(get_wallet_service),
):
    _wallet_rate_limit(user_id)
    wallet = svc.create_wallet(user_id=user_id, currency=payload.currency)
    return success_response({"id": wallet.id, "currency": wallet.currency, "balance": str(wallet.balance)})


@router.get("/balance/{currency}")
async def get_balance(
    currency: str,
    user_id: str = Depends(get_current_user_id),
    svc: AsyncWalletService = Depends(get_async_wallet_service),
):
    _wallet_rate_limit(user_id)
    currency_upper = currency.upper()
    try:
        balance = await svc.get_balance(user_id, currency_upper)
    except WalletNotFoundError:
        await svc.create_wallet(user_id=user_id, currency=currency_upper)
        balance = Decimal("0")
    return success_response({"currency": currency_upper, "balance": str(balance)})


@router.get("/transactions/{currency}")
async def list_transactions(
    currency: str,
    limit: int = 50,
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
    svc: AsyncWalletService = Depends(get_async_wallet_service),
):
    _wallet_rate_limit(user_id)
    currency_upper = currency.upper()
    try:
        page = await svc.list_transactions(user_id, currency_upper, limit=limit, offset=offset)
    except WalletNotFoundError:
        await svc.create_wallet(user_id=user_id, currency=currency_upper)
        page = []
    return success_response(
        [
            {
                "id": tx.id,
                "type": tx.type,
                "amount": str(tx.amount),
                "currency": currency_upper,
                "status": tx.status,
                "reference": tx.reference,
                "provider": tx.provider,
                "created_at": tx.created_at.isoformat(),
            }
            for tx in page
        ]
    )


@router.get("/summary")
async def wallet_summary(
    user_id: str = Depends(get_current_user_id),
    svc: AsyncWalletService = Depends(get_async_wallet_service),
):
    """Return all wallets for the current user with balances."""
    _wallet_rate_limit(user_id)
    wallets = await svc.list_wallets(user_id)
    # Auto-create XOF wallet on first call if none exist
    if not wallets:
        w = await svc.create_wallet(user_id=user_id, currency="XOF")
        wallets = [w]
    return success_response(
        [
            {"currency": w.currency, "balance": str(w.balance)}
            for w in wallets
        ]
    )


@router.get("/splits")
def list_split_history(
    currency: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
    svc: WalletService = Depends(get_wallet_service),
):
    _wallet_rate_limit(user_id)
    history = svc.list_split_history(user_id=user_id, currency=currency, limit=limit, offset=offset)
    return success_response(history)


@router.get("/social-protection")
def social_protection_dashboard(
    user_id: str = Depends(get_current_user_id),
    svc: WalletService = Depends(get_wallet_service),
):
    _wallet_rate_limit(user_id)
    user = svc.db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if user.role != "tasker":
        raise HTTPException(status_code=403, detail="Réservé aux taskers.")
    return success_response(svc.get_social_protection_overview(user_id))


@router.post("/credit")
def credit(
    payload: CreditPayload,
    admin_user_id: str = Depends(require_admin),
    svc: WalletService = Depends(get_wallet_service),
):
    """Admin-only: credit any user's wallet. Used for support adjustments and internal ops."""
    _wallet_rate_limit(admin_user_id)
    try:
        tx = svc.credit_wallet(
            user_id=payload.target_user_id,
            currency=payload.currency,
            amount=payload.decimal_amount(),
            reference=payload.reference,
            provider=payload.provider,
        )
        return success_response({
            "tx_id": tx.id,
            "target_user_id": payload.target_user_id,
            "type": "credit",
            "amount": str(tx.amount),
            "credited_by_admin": admin_user_id,
        })
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/escrow")
def create_escrow(
    payload: EscrowCreatePayload,
    user_id: str = Depends(require_kyc_approved),
    svc: WalletService = Depends(get_wallet_service),
):
    _assert_payments_enabled()
    _wallet_rate_limit(user_id)
    try:
        escrow = svc.create_escrow(
            task_id=payload.task_id,
            payer_id=user_id,
            payee_id=payload.payee_id,
            amount=payload.decimal_amount(),
            currency=payload.currency.upper(),
        )
        return success_response(
            {
                "escrow_id": escrow.id,
                "task_id": escrow.task_id,
                "amount": str(escrow.amount),
                "currency": escrow.currency,
                "status": escrow.status,
            }
        )
    except (InsufficientFundsError, WalletNotFoundError) as exc:
        raise HTTPException(status_code=402, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/escrow/{escrow_id}/release")
def release_escrow(
    escrow_id: str,
    user_id: str = Depends(get_current_user_id),
    svc: WalletService = Depends(get_wallet_service),
):
    _assert_payments_enabled()
    _wallet_rate_limit(user_id)
    try:
        escrow = svc.get_escrow(escrow_id)
        if escrow.payer_id != user_id:
            raise HTTPException(status_code=403, detail="Non autorise : vous n'etes pas le payeur de cet escrow")
        PaymentSafetyLayer(svc.db).assert_payout_safe(user_id=user_id)
        released = svc.release_escrow_safe(escrow_id)
        svc.finalize_transaction(released.id)
        return success_response({"escrow_id": escrow_id, "status": released.status})
    except PaymentSafetyError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except EscrowError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/escrow/{escrow_id}/refund")
def refund_escrow(
    escrow_id: str,
    user_id: str = Depends(get_current_user_id),
    svc: WalletService = Depends(get_wallet_service),
):
    _assert_payments_enabled()
    _wallet_rate_limit(user_id)
    try:
        escrow = svc.get_escrow(escrow_id)
        if escrow.payer_id != user_id:
            raise HTTPException(status_code=403, detail="Non autorise : vous n'etes pas le payeur de cet escrow")
        escrow = svc.refund_escrow(escrow_id)
        svc.finalize_transaction(escrow.id)
        return success_response({"escrow_id": escrow.id, "status": escrow.status})
    except EscrowError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


class WithdrawPayload(BaseModel):
    amount: str
    currency: str
    provider: str       # tmoney | flooz | orange_money | wave | mtn_momo | mpesa | ...
    phone_number: str
    country_code: str

    def decimal_amount(self) -> Decimal:
        try:
            return Decimal(self.amount)
        except InvalidOperation as exc:
            raise ValueError("Montant invalide") from exc


class PaymentMethodPayload(BaseModel):
    method_type: str = "mobile_money"
    provider: str
    phone_number: str
    country_code: str
    nickname: str | None = None
    is_default: bool = False


def _make_limits() -> TransactionLimits:
    return TransactionLimits(fx_rate_usd_to_xof=get_live_fx_rate())


@router.post("/withdraw")
async def withdraw(
    payload: WithdrawPayload,
    user_id: str = Depends(require_kyc_approved),
    svc: WalletService = Depends(get_wallet_service),
):
    """
    Retrait Mobile Money.

    Flow :
      1. Vérification limites journalières + détection cycle rapide
      2. Débit wallet + création Payout record (processing) — UN SEUL commit atomique
      3. Appel API payout (FedaPay ou Flutterwave)  → Payout processing
      4. Si payout OK  → Payout completed
      5. Si payout KO  → Payout failed + re-crédit wallet (rollback) + 502
    """
    _assert_payments_enabled()
    _wallet_rate_limit(user_id)

    amount = payload.decimal_amount()
    currency = payload.currency.upper()
    cc = payload.country_code.upper()
    reference = f"withdraw:{uuid.uuid4().hex[:16]}"

    # ── Limites journalières + détection cycle rapide ──────────────────────────
    limits = _make_limits()
    try:
        limits.check_and_record_withdrawal_daily(
            user_id=user_id,
            amount=amount,
            currency=currency,
            max_usd=Decimal(str(settings.max_withdrawal_per_day_usd)),
        )
        limits.check_rapid_cycle(
            user_id=user_id,
            window_minutes=settings.rapid_cycle_window_minutes,
        )
    except LimitExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except FraudDetected as exc:
        logger.warning("fraud:rapid_cycle user={} ref={}", user_id, reference)
        FinancialAuditLogger.log(
            action="fraud_rapid_cycle",
            user_id=user_id,
            payment_id=reference,
            amount=amount,
            currency=currency,
            provider=payload.provider,
            status="blocked",
            db=svc.db,
        )
        raise HTTPException(status_code=403, detail=str(exc))

    # ── Débit wallet + création du Payout dans UNE SEULE transaction atomique ──
    # Règle fintech absolue : jamais de Payout record sans débit correspondant,
    # et jamais de débit sans Payout. Les deux écritures partagent le même
    # commit (create_withdrawal_payout) : un crash avant le commit ne modifie
    # rien (rollback complet), un crash après le commit laisse les deux lignes
    # cohérentes. Il n'existe plus de fenêtre intermédiaire orpheline.
    try:
        debit_tx, payout_record = svc.create_withdrawal_payout(
            user_id=user_id,
            currency=currency,
            amount=amount,
            reference=reference,
            provider=payload.provider,
            phone_number=payload.phone_number,
            country_code=cc,
            metadata={
                "type": "withdrawal",
                "provider": payload.provider,
                "country_code": cc,
            },
        )
    except InsufficientFundsError as exc:
        raise HTTPException(status_code=402, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except PayoutCreationFailedException as exc:
        logger.error("payout:creation_failed user={} ref={} error={}", user_id, reference, exc)
        raise HTTPException(status_code=503, detail="Retrait indisponible — veuillez réessayer")

    payout_id = payout_record.id

    # ── Step 2 : appel API payout ──────────────────────────────────────────────
    try:
        payout_result = await execute_mobile_money_payout(
            user_id=user_id,
            amount=amount,
            currency=currency,
            provider=payload.provider,
            phone_number=payload.phone_number,
            country_code=cc,
            reference=reference,
        )

        # ── Payout record → completed / pending ────────────────────────────────
        payout_record.status = payout_result["status"]   # "completed" | "pending"
        payout_record.provider_tx_id = payout_result["provider_tx_id"]
        svc.db.commit()

        limits.clear_payout_failures(user_id=user_id)
        FinancialAuditLogger.log(
            action="payout_sent",
            user_id=user_id,
            payment_id=payout_result["provider_tx_id"],
            amount=amount,
            currency=currency,
            provider=payout_result["provider"],
            status=payout_result["status"],
            db=svc.db,
        )
        logger.info(
            "payout:sent user={} amount={} {} provider={} provider_tx={} ref={} payout_id={}",
            user_id, amount, currency, payout_result["provider"],
            payout_result["provider_tx_id"], reference, payout_id,
        )

    except PaymentProviderError as exc:
        # ── Payout record → failed ─────────────────────────────────────────────
        payout_record.status = "failed"
        payout_record.failure_reason = str(exc)
        svc.db.commit()

        # Rollback : re-crédit wallet
        logger.error(
            "payout:failed user={} ref={} payout_id={} error={}",
            user_id, reference, payout_id, exc,
        )
        try:
            svc.credit_wallet(
                user_id=user_id,
                currency=currency,
                amount=amount,
                reference=f"rollback:{reference}",
                provider="internal",
                metadata={
                    "type": "payout_rollback",
                    "original_tx": debit_tx.id,
                    "payout_id": payout_id,
                    "error": str(exc),
                },
            )
        except Exception as rollback_exc:
            logger.error(
                "payout:rollback_failed CRITICAL tx={} payout_id={} error={}",
                debit_tx.id, payout_id, rollback_exc,
            )

        FinancialAuditLogger.log(
            action="payout_failed",
            user_id=user_id,
            payment_id=reference,
            amount=amount,
            currency=currency,
            provider=payload.provider,
            status="failed",
            db=svc.db,
        )

        # Record failure for fraud detection — may raise FraudDetected
        try:
            limits.record_payout_failure(
                user_id=user_id,
                threshold=settings.payout_fail_block_threshold,
            )
        except FraudDetected as fraud_exc:
            logger.warning(
                "fraud:payout_block user={} reason={}",
                user_id, fraud_exc,
            )

        raise HTTPException(
            status_code=502,
            detail=f"Payout échoué — aucun débit définitif : {exc}",
        )

    return success_response({
        "payout_id": payout_id,
        "tx_id": debit_tx.id,
        "status": payout_result["status"],
        "provider": payout_result["provider"],
        "provider_tx_id": payout_result["provider_tx_id"],
        "amount": str(amount),
        "currency": currency,
        "reference": reference,
    })


@router.get("/payment-methods")
def list_payment_methods(
    user_id: str = Depends(get_current_user_id),
    svc: WalletService = Depends(get_wallet_service),
):
    _wallet_rate_limit(user_id)
    methods = svc.list_payment_methods(user_id)
    return success_response([
        {
            "id": m.id,
            "method_type": m.method_type,
            "provider": m.provider,
            "phone_number": m.phone_number,
            "country_code": m.country_code,
            "nickname": m.nickname,
            "details": m.details,
            "is_default": m.is_default,
        }
        for m in methods
    ])


@router.post("/payment-methods")
def add_payment_method(
    payload: PaymentMethodPayload,
    user_id: str = Depends(get_current_user_id),
    svc: WalletService = Depends(get_wallet_service),
):
    _wallet_rate_limit(user_id)
    method = svc.add_payment_method(
        user_id=user_id,
        method_type=payload.method_type,
        provider=payload.provider,
        phone_number=payload.phone_number,
        country_code=payload.country_code.upper(),
        nickname=payload.nickname,
        is_default=payload.is_default,
    )
    return success_response({
        "id": method.id,
        "provider": method.provider,
        "phone_number": method.phone_number,
        "country_code": method.country_code,
        "nickname": method.nickname,
        "details": method.details,
        "is_default": method.is_default,
    })


@router.delete("/payment-methods/{method_id}")
def delete_payment_method(
    method_id: str,
    user_id: str = Depends(get_current_user_id),
    svc: WalletService = Depends(get_wallet_service),
):
    _wallet_rate_limit(user_id)
    try:
        svc.delete_payment_method(method_id, user_id)
        return success_response({"deleted": True})
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))



@router.get("/escrow/task/{task_id}")
def get_escrow_by_task(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    svc: WalletService = Depends(get_wallet_service),
):
    _wallet_rate_limit(user_id)
    escrow = svc.get_escrow_by_task(task_id)
    if not escrow:
        raise HTTPException(status_code=404, detail="Escrow introuvable pour cette tache")
    if user_id not in {escrow.payer_id, escrow.payee_id}:
        raise HTTPException(status_code=403, detail="Accès non autorisé à cet escrow")
    return success_response(
        {
            "escrow_id": escrow.id,
            "task_id": escrow.task_id,
            "payer_id": escrow.payer_id,
            "payee_id": escrow.payee_id,
            "amount": str(escrow.amount),
            "currency": escrow.currency,
            "status": escrow.status,
        }
    )


class DepositPayload(BaseModel):
    amount: str
    currency: str
    # "stripe" (default) | "mobile_money" | "fedapay" | "flutterwave"
    provider: str = "stripe"

    @field_validator("currency")
    @classmethod
    def upper_currency(cls, v: str) -> str:
        return v.upper()

    def decimal_amount(self) -> Decimal:
        try:
            v = Decimal(self.amount)
            if v <= Decimal("0"):
                raise ValueError
            return v
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Montant invalide") from exc

    def is_mobile_money(self) -> bool:
        return self.provider.lower() in ("mobile_money", "fedapay", "flutterwave")


class ConvertPayload(BaseModel):
    from_currency: str
    to_currency: str
    amount: str

    @field_validator("from_currency", "to_currency")
    @classmethod
    def upper_currency(cls, v: str) -> str:
        return v.upper()

    def decimal_amount(self) -> Decimal:
        try:
            v = Decimal(self.amount)
            if v <= Decimal("0"):
                raise ValueError
            return v
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Montant invalide") from exc


class TransferPayload(BaseModel):
    to_user_id: str
    amount: str
    currency: str
    note: str = ""

    @field_validator("currency")
    @classmethod
    def upper_currency(cls, v: str) -> str:
        return v.upper()

    def decimal_amount(self) -> Decimal:
        try:
            v = Decimal(self.amount)
            if v <= Decimal("0"):
                raise ValueError
            return v
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Montant invalide") from exc


_ZERO_DECIMAL_CURRENCIES = frozenset(
    {"XOF", "JPY", "KRW", "CLP", "GNF", "ISK", "MGA", "PYG", "RWF", "UGX", "VND", "XAF"}
)

_STRIPE_PLACEHOLDER_KEYS = {"sk_test_REMPLACER", "sk_live_REMPLACER", ""}


@router.post("/deposit")
async def deposit(
    payload: DepositPayload,
    user_id: str = Depends(require_kyc_not_rejected),
    svc: WalletService = Depends(get_wallet_service),
    country_code: str = Depends(get_country_code),
):
    """
    Wallet top-up.
    - PAYMENT_MODE=mock              → crédit direct (développement uniquement)
    - provider=mobile_money          → FedaPay (XOF) ou Flutterwave selon le pays
    - provider=stripe (défaut)       → Stripe Checkout Session
    """
    _assert_payments_enabled()
    _wallet_rate_limit(user_id)

    mode = str(settings.payment_mode).strip().lower()

    amount = payload.decimal_amount()
    currency_upper = payload.currency

    # ── Daily deposit limit check (applied in all modes) ──────────────────────
    limits = _make_limits()
    try:
        limits.check_and_record_deposit_daily(
            user_id=user_id,
            amount=amount,
            currency=currency_upper,
            max_usd=Decimal(str(settings.max_deposit_per_day_usd)),
        )
    except LimitExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc))

    if mode == "mock":
        env_norm = str(settings.env).strip().lower()
        if env_norm != "development":
            raise HTTPException(
                status_code=403,
                detail=f"PAYMENT_MODE=mock est interdit en env='{env_norm}'. Utilisez PAYMENT_MODE=sandbox.",
            )
        reference = f"deposit:{uuid.uuid4().hex[:16]}"
        try:
            tx = svc.credit_wallet(
                user_id=user_id,
                currency=currency_upper,
                amount=amount,
                reference=reference,
                provider="mock",
                metadata={"type": "deposit", "mode": "mock"},
            )
            limits.record_deposit_timestamp(user_id=user_id)
            FinancialAuditLogger.log(
                action="deposit_mock",
                user_id=user_id,
                payment_id=reference,
                amount=amount,
                currency=currency_upper,
                provider="mock",
                status="completed",
                db=svc.db,
            )
            logger.info(
                "deposit:mock user={} amount={} {} ref={}",
                user_id, amount, currency_upper, reference,
            )
            return success_response({
                "mode": "mock",
                "tx_id": tx.id,
                "amount": str(tx.amount),
                "currency": currency_upper,
                "reference": reference,
                "status": "completed",
            })
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    # ── Mobile Money (FedaPay / Flutterwave) ──────────────────────────────────
    if payload.is_mobile_money():
        reference = f"topup:{uuid.uuid4().hex[:16]}"
        effective_country = country_code or "TG"

        try:
            result = await create_mobile_money_topup(
                user_id=user_id,
                user_email="",
                amount=amount,
                currency=currency_upper,
                country_code=effective_country,
                reference=reference,
            )
        except PaymentProviderError as exc:
            logger.error("deposit:mobile_money_error user={} error={}", user_id, exc)
            raise HTTPException(status_code=502, detail=f"Erreur provider: {exc}")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        logger.info(
            "deposit:mobile_money_initiated user={} amount={} {} provider={} ref={}",
            user_id, amount, currency_upper, result["provider"], reference,
        )
        return success_response({
            "mode": "mobile_money",
            "provider": result["provider"],
            "payment_url": result["payment_url"],
            "provider_tx_id": result["provider_tx_id"],
            "reference": reference,
            "amount": str(amount),
            "currency": currency_upper,
        })

    # ── Stripe Checkout Session ────────────────────────────────────────────────
    if _stripe is None:
        raise HTTPException(status_code=503, detail="Package 'stripe' non installé")

    stripe_key = settings.stripe_secret_key.strip()
    if not stripe_key or stripe_key in _STRIPE_PLACEHOLDER_KEYS:
        raise HTTPException(
            status_code=503,
            detail="Stripe non configuré — renseigner STRIPE_SECRET_KEY dans .env (sk_test_...)",
        )

    _stripe.api_key = stripe_key  # type: ignore[union-attr]

    reference = f"topup:{uuid.uuid4().hex[:16]}"
    stripe_amount = int(amount) if currency_upper in _ZERO_DECIMAL_CURRENCIES else int(amount * 100)

    wallet_base = _wallet_frontend_url("/wallet")
    success_url = f"{wallet_base}?status=success&ref={reference}&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{wallet_base}?status=cancel"

    try:
        session = _stripe.checkout.Session.create(  # type: ignore[union-attr]
            mode="payment",
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": currency_upper.lower(),
                    "unit_amount": stripe_amount,
                    "product_data": {"name": f"ZASKA — Recharge portefeuille ({currency_upper})"},
                },
                "quantity": 1,
            }],
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=reference,
            metadata={
                "type": "wallet_topup",
                "user_id": user_id,
                "currency": currency_upper,
                "amount": str(amount),
                "reference": reference,
            },
        )
        logger.info(
            "deposit:stripe_checkout_created user={} amount={} {} ref={}",
            user_id, amount, currency_upper, reference,
        )
        return success_response({
            "mode": "stripe_checkout",
            "checkout_url": session.url,
            "session_id": session.id,
            "reference": reference,
            "amount": str(amount),
            "currency": currency_upper,
        })
    except Exception as exc:
        logger.error("deposit:stripe_checkout_failed user={} error={}", user_id, exc)
        raise HTTPException(status_code=502, detail=f"Erreur Stripe: {exc}")


@router.post("/transfer")
def transfer(
    payload: TransferPayload,
    user_id: str = Depends(require_kyc_approved),
    svc: WalletService = Depends(get_wallet_service),
):
    """Transfert interne entre utilisateurs — atomique, enregistré dans le ledger."""
    _wallet_rate_limit(user_id)
    if user_id == payload.to_user_id:
        raise HTTPException(status_code=400, detail="Transfert vers soi-même interdit")
    reference = uuid.uuid4().hex[:16]
    try:
        amount = payload.decimal_amount()
        currency = payload.currency
        debit_tx, _ = svc.transfer_atomic(
            from_user_id=user_id,
            to_user_id=payload.to_user_id,
            currency=currency,
            amount=amount,
            reference=reference,
            note=payload.note,
        )
        return success_response(
            {
                "reference": reference,
                "tx_id": debit_tx.id,
                "amount": str(amount),
                "currency": currency,
                "from_user_id": user_id,
                "to_user_id": payload.to_user_id,
                "status": "completed",
            }
        )
    except InsufficientFundsError as exc:
        raise HTTPException(status_code=402, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── FX Conversion ──────────────────────────────────────────────────────────────

@router.post("/convert")
def convert(
    payload: ConvertPayload,
    user_id: str = Depends(require_kyc_approved),
    svc: WalletService = Depends(get_wallet_service),
):
    """
    Convertit entre USD et XOF au taux fixe configuré (FX_USD_TO_XOF).
    Frais : FX_FEE_BPS basis points (défaut 50 bps = 0.5 %).
    Ledger : une transaction debit (source) + une transaction credit (destination).
    Limites : FX_MAX_PER_TX_USD par transaction, FX_MAX_DAILY_USD par jour.
    """
    _assert_payments_enabled()
    _wallet_rate_limit(user_id)

    from_cur = payload.from_currency
    to_cur = payload.to_currency

    if (from_cur, to_cur) not in {("USD", "XOF"), ("XOF", "USD")}:
        raise HTTPException(
            status_code=400,
            detail=f"Paire {from_cur}/{to_cur} non supportée — disponible : USD/XOF, XOF/USD",
        )

    from_amount = payload.decimal_amount()
    usd_to_xof = get_live_fx_rate()
    rate = usd_to_xof if (from_cur == "USD") else (Decimal("1") / usd_to_xof).quantize(Decimal("0.0000001"))

    # ── FX limits ──────────────────────────────────────────────────────────────
    limits = _make_limits()
    # direction: USD→XOF = selling XOF = "to_xof"; XOF→USD = buying XOF = "from_xof"
    exposure_direction = "to_xof" if from_cur == "USD" else "from_xof"
    from_amount_usd = (
        from_amount
        if from_cur == "USD"
        else (from_amount / usd_to_xof).quantize(Decimal("0.01"))
    )
    try:
        limits.check_fx_per_tx(
            user_id=user_id,
            amount=from_amount,
            currency=from_cur,
            max_usd=Decimal(str(settings.fx_max_per_tx_usd)),
        )
        limits.check_and_record_fx_daily(
            user_id=user_id,
            amount=from_amount,
            currency=from_cur,
            max_usd=Decimal(str(settings.fx_max_daily_usd)),
        )
        limits.check_and_record_fx_exposure(
            direction=exposure_direction,
            amount_usd=from_amount_usd,
            limit_usd=Decimal(str(settings.fx_exposure_limit_usd)),
        )
    except LimitExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc))

    reference = f"fx:{from_cur}:{to_cur}:{uuid.uuid4().hex[:12]}"
    try:
        debit_tx, credit_tx = svc.convert_currency(
            user_id=user_id,
            from_currency=from_cur,
            to_currency=to_cur,
            from_amount=from_amount,
            rate=rate,
            fee_bps=settings.fx_fee_bps,
            reference=reference,
        )
        to_amount_gross = (debit_tx.amount * rate).quantize(Decimal("0.01"))
        fee_amount = to_amount_gross - credit_tx.amount

        FinancialAuditLogger.log(
            action="fx_conversion",
            user_id=user_id,
            payment_id=reference,
            amount=from_amount,
            currency=from_cur,
            provider="internal",
            status="completed",
            db=svc.db,
        )
        logger.info(
            "fx:convert user={} {}{}→{}{} rate={} fee_bps={} ref={}",
            user_id, from_amount, from_cur, credit_tx.amount, to_cur,
            rate, settings.fx_fee_bps, reference,
        )

        return success_response({
            "source": "internal_fixed_rate",
            "from_currency": from_cur,
            "to_currency": to_cur,
            "from_amount": str(debit_tx.amount),
            "to_amount": str(credit_tx.amount),
            "fee_amount": str(fee_amount),
            "applied_rate": str(rate),
            "rate": str(rate),
            "fee_bps": settings.fx_fee_bps,
            "debit_tx_id": debit_tx.id,
            "credit_tx_id": credit_tx.id,
            "reference": reference,
            "status": "completed",
        })
    except InsufficientFundsError as exc:
        raise HTTPException(status_code=402, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

"""
MockProvider — simulation de paiement pour le mode dev.

Règles :
  - Aucun appel réseau externe
  - Retourne un payment_url pointant vers l'endpoint /payments/mock/success
  - handle_success / handle_failure : même contrat que les providers réels
  - Idempotence obligatoire (double success → pas de double crédit)

Utilisation :
  Activé automatiquement quand PAYMENT_MODE=dev dans .env.
  Ne jamais instancier directement en sandbox/production.
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from app.core.config import settings

from .base_provider import (
    PaymentIntentResult,
    PaymentProvider,
    WebhookEvent,
)

if TYPE_CHECKING:
    from app.services.wallet_service import WalletService


class MockProvider(PaymentProvider):
    """
    Provider de simulation — mode dev uniquement.

    Flux :
      1. create_payment_intent() → payment_url = /payments/mock/success?escrow_id=...
      2. Développeur POST /payments/mock/success {"escrow_id": "..."}
      3. handle_success() → fund_escrow_from_payment() via WalletService
    """

    PROVIDER_NAME = "mock"

    async def create_payment_intent(
        self,
        *,
        amount: Decimal,
        currency: str,
        user_id: str,
        user_email: str,
        escrow_id: str,
        task_id: str,
        task_description: str,
        country_code: str,
        idempotency_key: str,
    ) -> PaymentIntentResult:
        from app.core.observability import logger

        mock_id = f"mock_{uuid.uuid4().hex[:12]}"
        base = settings.payment_webhook_base_url.rstrip("/")
        # payment_url pointe vers l'endpoint /payments/mock/success
        payment_url = f"{base}/api/payments/mock/success?escrow_id={escrow_id}"

        logger.info(
            "[mock] intent créé — id={} escrow={} amount={} {} country={} [PAYMENT_MODE=dev]",
            mock_id, escrow_id, amount, currency, country_code,
        )

        return PaymentIntentResult(
            provider_intent_id=mock_id,
            provider="mock",
            amount=amount,
            currency=currency,
            client_secret=None,
            payment_url=payment_url,
            escrow_id=escrow_id,
            idempotency_key=idempotency_key,
        )

    async def verify_webhook(
        self,
        raw_body: bytes,
        headers: dict[str, str],
    ) -> WebhookEvent:
        """
        MockProvider ne reçoit pas de vrais webhooks.
        Cette méthode parse un payload JSON minimaliste pour les tests.
        """
        try:
            body = json.loads(raw_body)
        except (json.JSONDecodeError, ValueError):
            body = {}

        escrow_id: str = body.get("escrow_id", "")
        event_type: str = body.get("event_type", "payment.success")

        return WebhookEvent(
            event_type=event_type,
            provider_tx_id=f"mock_{uuid.uuid4().hex[:8]}",
            escrow_id=escrow_id,
            amount=Decimal(str(body.get("amount", 0))),
            currency=body.get("currency", ""),
            raw_data=body,
        )

    async def handle_success(
        self,
        event: WebhookEvent,
        wallet_svc: WalletService,
    ) -> None:
        """
        Simulation de paiement réussi : finance l'escrow.
        Idempotent — double appel ignoré.

        NE JAMAIS appeler wallet_svc directement depuis une route.
        Cette méthode est le seul point de contact autorisé.
        """
        from app.core.observability import logger
        from app.services.wallet_service import EscrowError

        if not event.escrow_id:
            logger.warning("[mock] handle_success: escrow_id absent — ignoré")
            return

        try:
            wallet_svc.fund_escrow_from_payment(
                escrow_id=event.escrow_id,
                provider="mock",
                provider_tx_id=event.provider_tx_id,
            )
            logger.info(
                "[mock] handle_success: escrow {} financé (simulation) [PAYMENT_MODE=dev]",
                event.escrow_id,
            )
        except EscrowError as exc:
            # Idempotence : déjà funded ou cancelled → log et ignorer
            logger.warning("[mock] handle_success idempotent — {}", exc)

    async def handle_failure(
        self,
        event: WebhookEvent,
        wallet_svc: WalletService,
    ) -> None:
        """Simulation de paiement échoué : annule l'escrow pending."""
        from app.core.observability import logger
        from app.services.wallet_service import EscrowError

        if not event.escrow_id:
            return

        try:
            wallet_svc.cancel_pending_escrow(event.escrow_id)
            logger.warning(
                "[mock] handle_failure: escrow {} annulé (simulation) [PAYMENT_MODE=dev]",
                event.escrow_id,
            )
        except EscrowError as exc:
            logger.warning("[mock] handle_failure idempotent — {}", exc)

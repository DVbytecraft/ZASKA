"""
Interface abstraite pour tous les providers de paiement ZASKA.

Règles d'implémentation :
  - Toute exception provider → lever PaymentProviderError (ne jamais laisser fuiter)
  - Le montant DOIT toujours être recalculé côté serveur, jamais depuis le frontend
  - verify_webhook() est la SOURCE DE VÉRITÉ — aucun crédit sans webhook confirmé
  - handle_success / handle_failure : seuls points de contact avec WalletService
    → les routes n'appellent JAMAIS wallet_service directement
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.wallet_service import WalletService


# ── Résultats et événements ───────────────────────────────────────────────────

@dataclass
class PaymentIntentResult:
    provider_intent_id: str
    provider: str                   # stripe | fedapay | flutterwave
    amount: Decimal
    currency: str
    client_secret: str | None       # Stripe Elements — null pour FedaPay/FLW
    payment_url: str | None         # FedaPay / Flutterwave redirect — null pour Stripe
    escrow_id: str
    idempotency_key: str


@dataclass
class PayoutResult:
    provider: str
    payout_id: str
    status: str          # "processing" | "completed" | "failed"
    amount: Decimal
    currency: str
    raw: dict = field(default_factory=dict)


@dataclass
class WebhookEvent:
    event_type: str                 # "payment.success" | "payment.failed" | "unhandled"
    provider_tx_id: str
    escrow_id: str
    amount: Decimal
    currency: str
    raw_data: dict = field(default_factory=dict)


# ── Exceptions ────────────────────────────────────────────────────────────────

class InvalidWebhookSignature(Exception):
    """Signature webhook invalide ou absente — requête à rejeter (HTTP 400)."""


class PaymentProviderError(Exception):
    """Erreur renvoyée par le provider externe (API down, config invalide…)."""


class UnsupportedCountryError(Exception):
    def __init__(self, country_code: str, provider_name: str) -> None:
        super().__init__(
            f"Provider '{provider_name}' non implémenté pour le pays '{country_code}'"
        )
        self.country_code = country_code
        self.provider_name = provider_name


# ── Interface ─────────────────────────────────────────────────────────────────

class PaymentProvider(ABC):
    """
    Contrat que tout provider doit respecter.

    Cycle de vie :
      1. create_payment_intent()  → retourne client_secret ou payment_url
      2. [paiement côté utilisateur]
      3. verify_webhook()         → retourne WebhookEvent (success ou failure)
      4. handle_success / handle_failure → crédite ou annule l'escrow via WalletService

    Les routes n'appellent JAMAIS wallet_service directement.
    Toute interaction financière passe par handle_success / handle_failure.
    """

    # Nom du provider — chaque sous-classe DOIT le surcharger
    PROVIDER_NAME: str = "base"

    @abstractmethod
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
    ) -> PaymentIntentResult: ...

    @abstractmethod
    async def verify_webhook(
        self,
        raw_body: bytes,
        headers: dict[str, str],
    ) -> WebhookEvent: ...

    async def payout(
        self,
        *,
        amount: Decimal,
        currency: str,
        recipient_phone: str,
        country_code: str,
        reference: str,
        idempotency_key: str,
    ) -> PayoutResult:
        """Initiate a payout to a mobile money / bank account.

        Default implementation raises NotImplementedError.
        Providers that support payout MUST override this method.
        """
        raise NotImplementedError(
            f"Provider '{self.PROVIDER_NAME}' does not support direct payout. "
            "Use the payout worker or a dedicated payout provider."
        )

    # ── Handlers financiers — implémentation par défaut ───────────────────────

    async def handle_success(
        self,
        event: WebhookEvent,
        wallet_svc: WalletService,
    ) -> None:
        """
        Finance l'escrow suite à un paiement confirmé.
        Idempotent : si l'escrow est déjà funded, log et retourne sans erreur.

        Les routes ne doivent JAMAIS appeler wallet_service directement.
        """
        # Import lazy pour éviter tout risque de circularité au module load
        from app.core.observability import logger
        from app.services.wallet_service import EscrowError

        if not event.escrow_id:
            logger.warning(
                "[{}] handle_success: escrow_id absent dans l'event — ignoré",
                self.PROVIDER_NAME,
            )
            return
        try:
            wallet_svc.fund_escrow_from_payment(
                escrow_id=event.escrow_id,
                provider=self.PROVIDER_NAME,
                provider_tx_id=event.provider_tx_id,
            )
            logger.info(
                "[{}] handle_success: escrow {} financé",
                self.PROVIDER_NAME, event.escrow_id,
            )
        except EscrowError as exc:
            logger.warning("[{}] handle_success idempotent: {}", self.PROVIDER_NAME, exc)

    async def handle_failure(
        self,
        event: WebhookEvent,
        wallet_svc: WalletService,
    ) -> None:
        """
        Annule l'escrow pending suite à un paiement échoué.
        Idempotent : si l'escrow est déjà cancelled, log et retourne sans erreur.
        """
        from app.core.observability import logger
        from app.services.wallet_service import EscrowError

        if not event.escrow_id:
            return
        try:
            wallet_svc.cancel_pending_escrow(event.escrow_id)
            logger.warning(
                "[{}] handle_failure: escrow {} annulé",
                self.PROVIDER_NAME, event.escrow_id,
            )
        except EscrowError as exc:
            logger.warning("[{}] handle_failure idempotent: {}", self.PROVIDER_NAME, exc)

"""
PaymentRouterService — décide quel provider utiliser selon le pays.

Règles de routage :
  - Zone EU      → Stripe + Apple Pay + Google Pay
  - Zone CFA     → FedaPay + Mobile Money (XOF)
  - Ghana        → Flutterwave + MTN MoMo (GHS)
  - Nigeria + autres Flutterwave → Flutterwave + Card
  - Fallback     → Stripe international (safe mode)

Aucune logique métier ne doit appeler les providers directement.
Tout passe par cette couche.
"""

from __future__ import annotations

from pydantic import BaseModel

from .definitions import CFA_ZONE, EU_ZONE, FLUTTERWAVE_ZONE


class PaymentRoute(BaseModel, frozen=True):
    provider: str              # stripe | fedapay | flutterwave | mock
    method: str                # card | mobile_money
    apple_pay_enabled: bool
    google_pay_enabled: bool
    region: str                # EU | WAF_CFA | WAF | INTL
    currency: str
    commission_rate: float     # taux plateforme (0.15 = 15%)
    description: str

    def available_methods(self) -> list[str]:
        """Liste des méthodes UX disponibles pour ce contexte."""
        methods = [self.method]
        if self.apple_pay_enabled:
            methods.append("apple_pay")
        if self.google_pay_enabled:
            methods.append("google_pay")
        return methods


class PaymentRouterService:
    """
    Service sans état — toutes les méthodes sont statiques.
    Instancier si nécessaire via DI, ou appeler statiquement.
    """

    DEFAULT_COMMISSION = 0.15  # 15 % plateforme

    @staticmethod
    def route_payment(country_code: str, amount: float, currency: str) -> PaymentRoute:
        """
        Retourne la route de paiement optimale pour un pays donné.

        Args:
            country_code: Code ISO 3166-1 alpha-2 (ex: "TG", "FR").
            amount: Montant (utilisé pour logiques de seuil futures).
            currency: Devise ISO 4217 souhaitée.
        """
        cc = country_code.upper()

        # ── Zone EU : Stripe + Apple/Google Pay ───────────────────────────
        if cc in EU_ZONE:
            return PaymentRoute(
                provider="stripe",
                method="card",
                apple_pay_enabled=True,
                google_pay_enabled=True,
                region="EU",
                currency=currency or "EUR",
                commission_rate=PaymentRouterService.DEFAULT_COMMISSION,
                description="Stripe EU — carte, Apple Pay, Google Pay disponibles",
            )

        # ── Zone CFA : FedaPay + Mobile Money ─────────────────────────────
        if cc in CFA_ZONE:
            return PaymentRoute(
                provider="fedapay",
                method="mobile_money",
                apple_pay_enabled=False,
                google_pay_enabled=False,
                region="WAF_CFA",
                currency="XOF",
                commission_rate=PaymentRouterService.DEFAULT_COMMISSION,
                description="FedaPay — Mobile Money (Orange, MTN, Moov)",
            )

        # ── Ghana : Flutterwave + MTN MoMo ────────────────────────────────
        if cc == "GH":
            return PaymentRoute(
                provider="flutterwave",
                method="mobile_money",
                apple_pay_enabled=False,
                google_pay_enabled=False,
                region="WAF",
                currency="GHS",
                commission_rate=PaymentRouterService.DEFAULT_COMMISSION,
                description="Flutterwave — MTN MoMo Ghana",
            )

        # ── Nigeria + reste zone Flutterwave ──────────────────────────────
        if cc in FLUTTERWAVE_ZONE:
            currency_map = {
                "NG": "NGN",
                "KE": "KES",
                "ZA": "ZAR",
                "TZ": "TZS",
                "UG": "UGX",
                "RW": "RWF",
            }
            return PaymentRoute(
                provider="flutterwave",
                method="card",
                apple_pay_enabled=False,
                google_pay_enabled=False,
                region="WAF",
                currency=currency_map.get(cc, currency or "USD"),
                commission_rate=PaymentRouterService.DEFAULT_COMMISSION,
                description=f"Flutterwave — carte {cc}",
            )

        # ── Fallback international : Stripe ───────────────────────────────
        return PaymentRoute(
            provider="stripe",
            method="card",
            apple_pay_enabled=True,
            google_pay_enabled=True,
            region="INTL",
            currency=currency or "USD",
            commission_rate=PaymentRouterService.DEFAULT_COMMISSION,
            description="Stripe international — fallback sécurisé",
        )

    @staticmethod
    def compute_commission(amount: float, country_code: str) -> dict[str, float]:
        """Décompose montant → commission plateforme + montant escrow."""
        route = PaymentRouterService.route_payment(country_code, amount, "")
        commission = round(amount * route.commission_rate, 2)
        escrow = round(amount - commission, 2)
        return {
            "total": amount,
            "commission": commission,
            "escrow_amount": escrow,
            "commission_rate": route.commission_rate,
            "provider": route.provider,
        }

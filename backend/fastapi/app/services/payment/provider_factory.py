"""
PaymentProviderFactory — sélection du provider selon le mode et le pays.

Modes (PAYMENT_MODE dans .env) :
  dev        → MockProvider systématiquement — aucun appel externe
  sandbox    → providers réels avec clés test (sk_test_, sk_sandbox_)
  production → providers réels avec clés live

Logique pays (sandbox/production) :
  1. get_provider(country_code) lit CountryConfig.payment_providers[0]
  2. Résout le nom de provider → classe concrète via PROVIDER_CLASS_MAP
  3. Toute la logique pays est dans le registre CountryConfig (definitions.py)

Ajouter un nouveau provider = 1 ligne dans PROVIDER_CLASS_MAP + 1 import.
Aucun code pays hardcodé ici.
"""

from __future__ import annotations

from typing import Callable

from app.core.country_engine.definitions import get_config

from .base_provider import PaymentProvider, UnsupportedCountryError
from .fedapay_provider import FedaPayProvider
from .flutterwave_provider import FlutterwaveProvider
from .paystack_provider import PaystackProvider
from .stripe_provider import StripeProvider

# Registre nom_provider → factory callable (sandbox et production)
# Adding a new provider = 1 line here + 1 import above. No other changes needed.
PROVIDER_CLASS_MAP: dict[str, Callable[[], PaymentProvider]] = {
    "stripe": StripeProvider,
    "fedapay": FedaPayProvider,
    "flutterwave": FlutterwaveProvider,
    "paystack": PaystackProvider,
}


def get_provider(country_code: str) -> PaymentProvider:
    """
    Retourne le provider approprié selon PAYMENT_MODE et country_code.

    - dev        → MockProvider (aucun appel réseau)
    - sandbox    → provider du pays avec clés test
    - production → provider du pays avec clés live

    Raises UnsupportedCountryError si le provider n'est pas implémenté.
    """
    from app.core.config import settings

    # Mode dev : toujours MockProvider, indépendamment du pays
    if settings.payment_mode in {"dev", "mock"}:
        from .mock_provider import MockProvider
        return MockProvider()

    # sandbox | production : routage basé sur CountryConfig (aucun pays hardcodé)
    config = get_config(country_code)
    if not config.payment_providers:
        raise UnsupportedCountryError(country_code, "none")

    primary_name = config.payment_providers[0]
    factory_fn = PROVIDER_CLASS_MAP.get(primary_name)
    if factory_fn is None:
        raise UnsupportedCountryError(country_code, primary_name)

    return factory_fn()


def list_supported_countries() -> dict[str, str]:
    """Retourne {country_code: provider_name} pour les pays avec provider implémenté."""
    from app.core.country_engine.definitions import COUNTRY_REGISTRY
    result: dict[str, str] = {}
    for cc, cfg in COUNTRY_REGISTRY.items():
        if cc == "DEFAULT":
            continue
        if cfg.payment_providers:
            provider = cfg.payment_providers[0]
            if provider in PROVIDER_CLASS_MAP:
                result[cc] = provider
    return result

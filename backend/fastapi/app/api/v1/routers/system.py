"""
GET /api/system/bootstrap

Endpoint public (pas de JWT requis) renvoyant la configuration runtime
adaptée au pays de l'appelant. Consommé au démarrage de l'application
frontale pour éviter tout hardcoding pays/devise/provider dans le client.

Réponse :
{
  "country": "TG",
  "currency": "XOF",
  "payment_methods": ["mobile_money", "fedapay"],
  "payment_route": { "provider": "fedapay", ... },
  "kyc_provider": "smile_identity",
  "sms_gateway": "africas_talking",
  "mobile_money_enabled": true,
  "stripe_enabled": false,
  "escrow_enabled": true,
  "payout_delay_minutes": 1440,
  "features": { "mobile_money": true, ... },
  "timezone": "Africa/Lome",
  "emergency_numbers": { "police": "117", ... }
}
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.country_engine import (
    CountryEngineService,
    FeatureFlagEngine,
    PaymentRouterService,
)
from app.core.config import settings
from app.core.redis_client import redis_sync
from app.core.responses import success_response
from app.db.session import get_db
from app.services.geo_hierarchy_service import GeoHierarchyService
from app.services.module_control_service import ModuleControlService

router = APIRouter(prefix="/system", tags=["system"])


def _get_cre() -> CountryEngineService:
    return CountryEngineService(redis_sync)


@router.get("/bootstrap")
def bootstrap(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Retourne la configuration runtime complète pour le pays détecté.
    Détection : header X-Country-Code > IP > fallback EU (FR).
    Aucune authentification requise (appelé avant login).
    """
    cre = _get_cre()
    country_code = cre.detect_country_from_request(request)
    config = cre.get_country_config(country_code)

    route = PaymentRouterService.route_payment(country_code, 0, config.currency)
    flags = FeatureFlagEngine(redis_sync, db).get_flags(country_code)
    modules = ModuleControlService(db).resolve_modules_for_country(country_code)
    geo = GeoHierarchyService(db).resolve_country_geo(country_code)

    return success_response(
        {
            "country": country_code,
            "currency": config.currency,
            "payment_methods": config.payment_methods,
            "payment_route": route.model_dump(),
            "kyc_provider": config.kyc_provider,
            "sms_gateway": config.sms_gateway,
            "mobile_money_enabled": config.mobile_money_enabled,
            "stripe_enabled": config.stripe_enabled,
            "escrow_enabled": config.escrow_enabled,
            "payout_delay_minutes": config.payout_delay_minutes,
            "features": flags,
            "modules": modules,
            "geo": geo,
            "timezone": config.timezone,
            "emergency_numbers": config.emergency_numbers,
        }
    )


@router.get("/bootstrap/{country_code}")
def bootstrap_for_country(
    country_code: str,
    db: Session = Depends(get_db),
):
    """
    Variante explicite : retourne la config pour un pays précis.
    Utile pour l'admin dashboard et les tests d'intégration.
    """
    cre = _get_cre()
    cc = country_code.upper()
    config = cre.get_country_config(cc)

    route = PaymentRouterService.route_payment(cc, 0, config.currency)
    flags = FeatureFlagEngine(redis_sync, db).get_flags(cc)
    modules = ModuleControlService(db).resolve_modules_for_country(cc)
    geo = GeoHierarchyService(db).resolve_country_geo(cc)

    return success_response(
        {
            "country": cc,
            "currency": config.currency,
            "payment_methods": config.payment_methods,
            "payment_route": route.model_dump(),
            "kyc_provider": config.kyc_provider,
            "sms_gateway": config.sms_gateway,
            "mobile_money_enabled": config.mobile_money_enabled,
            "stripe_enabled": config.stripe_enabled,
            "escrow_enabled": config.escrow_enabled,
            "payout_delay_minutes": config.payout_delay_minutes,
            "features": flags,
            "modules": modules,
            "geo": geo,
            "timezone": config.timezone,
            "emergency_numbers": config.emergency_numbers,
        }
    )


@router.get("/payment-status")
def payment_status(
    country_code: str = "FR",
    db: Session = Depends(get_db),
):
    cc = country_code.upper()
    flags = FeatureFlagEngine(redis_sync, db).get_flags(cc)
    real_money_enabled = bool(settings.real_money_enabled and flags.get("real_money_enabled", False))

    providers = {
        "stripe": "ready" if (settings.stripe_secret_key.strip() and settings.stripe_webhook_secret.strip()) else "missing_config",
        "fedapay": "ready" if (settings.fedapay_api_key.strip() and settings.fedapay_webhook_secret.strip()) else "missing_config",
        "flutterwave": "ready" if (settings.flutterwave_secret_key.strip() and settings.flutterwave_hash.strip()) else "missing_config",
    }
    return success_response(
        {
            "mode": settings.payment_mode,
            "real_money_enabled": real_money_enabled,
            "payments_disabled": settings.payments_disabled,
            "providers": providers,
        }
    )

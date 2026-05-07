"""
CountryEngineService — point d'entrée central du Country Runtime Engine.

Responsabilités :
  - Détection du pays depuis la requête HTTP (header > IP > fallback EU)
  - Distribution vers les providers KYC / SMS / paiement corrects
  - Cache Redis pour éviter les résolutions répétées (TTL 1h)

L'IP-to-country est un stub : brancher MaxMind GeoIP2 (ou ip-api.com)
en remplaçant _detect_country_from_ip() pour la production.
"""

from __future__ import annotations

import ipaddress

from fastapi import Request
from redis import Redis

from .definitions import COUNTRY_REGISTRY, CountryConfig, get_config
from .payment_router import PaymentRoute, PaymentRouterService

# Préfixes RFC-1918 / loopback — pas de géolocalisation possible
_PRIVATE_NETS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]

_EU_SAFE_DEFAULT = "FR"


def _is_private(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        return any(addr in net for net in _PRIVATE_NETS)
    except ValueError:
        return True


def _detect_country_from_ip(ip: str) -> str | None:
    """
    Résolution IP → pays.
    Stub en attente d'intégration MaxMind / ip-api.
    En prod : `import geoip2.database; reader.country(ip).country.iso_code`
    """
    if _is_private(ip):
        return None
    # TODO: intégrer MaxMind GeoIP2 ou ip-api.com
    return None


class CountryEngineService:
    """
    Service principal du CRE.
    Doit être instancié avec le client Redis (redis_sync).
    Aucune dépendance SQLAlchemy — le CRE est stateless côté DB.
    """

    CONFIG_CACHE_TTL = 3600   # 1 heure
    HEADER_NAME = "X-Country-Code"
    FALLBACK_COUNTRY = _EU_SAFE_DEFAULT

    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client

    # ── Résolution config ──────────────────────────────────────────────────

    def get_country_config(self, country_code: str) -> CountryConfig:
        """
        Retourne la config pour country_code.
        Lecture depuis cache Redis ; écriture au miss (TTL 1h).
        Toujours retourne une config valide (fallback DEFAULT).
        """
        cc = country_code.upper()
        cache_key = f"country:{cc}"
        cached = self._redis.get(cache_key)
        if cached:
            return CountryConfig.model_validate_json(cached)

        config = get_config(cc)
        self._redis.setex(cache_key, self.CONFIG_CACHE_TTL, config.model_dump_json())
        return config

    # ── Détection pays depuis requête ─────────────────────────────────────

    def detect_country_from_request(self, request: Request) -> str:
        """
        Cascade de détection :
          1. Header X-Country-Code (validé contre le registre)
          2. IP géolocalisation (stub)
          3. Fallback : FR (safe EU mode)
        """
        # 1. Header explicite — validé syntaxiquement (2 lettres alpha)
        header = request.headers.get(self.HEADER_NAME, "").strip().upper()
        if len(header) == 2 and header.isalpha():
            # On accepte même les pays hors registre (DEFAULT sera appliqué dans get_config)
            return header

        # 2. IP-based
        client_ip = (request.client.host if request.client else None) or ""
        if client_ip:
            detected = _detect_country_from_ip(client_ip)
            if detected:
                return detected

        # 3. Safe fallback EU
        return self.FALLBACK_COUNTRY

    # ── Délégation vers providers ─────────────────────────────────────────

    def resolve_payment_route(
        self,
        country_code: str,
        amount: float = 0.0,
        currency: str = "",
    ) -> PaymentRoute:
        config = self.get_country_config(country_code)
        effective_currency = currency or config.currency
        return PaymentRouterService.route_payment(country_code, amount, effective_currency)

    def resolve_kyc_provider(self, country_code: str) -> str:
        return self.get_country_config(country_code).kyc_provider

    def resolve_sms_gateway(self, country_code: str) -> str:
        return self.get_country_config(country_code).sms_gateway

    # ── Gestion cache ─────────────────────────────────────────────────────

    def invalidate(self, country_code: str) -> None:
        """Force le rechargement de la config et des flags au prochain accès."""
        cc = country_code.upper()
        self._redis.delete(f"country:{cc}")
        self._redis.delete(f"features:{cc}")

    def warm_cache(self) -> list[str]:
        """
        Pré-charge en Redis toutes les configs du registre.
        Appeler au démarrage pour zéro cache-miss sur les premiers appels.
        """
        loaded: list[str] = []
        for cc, config in COUNTRY_REGISTRY.items():
            self._redis.setex(f"country:{cc}", self.CONFIG_CACHE_TTL, config.model_dump_json())
            loaded.append(cc)
        return loaded

"""
Runtime FX rate helper — all rates expressed as 1 USD = X currency (USD pivot).

Priority for each rate: Redis override (set by admin) > settings default (env var).
Admin endpoint: PUT /admin/fx/rate {"rate": "655.957"}  (XOF only, legacy)
For other currencies admins can SET the Redis key directly:
  SET config:fx_usd_to_ngn 1700
"""

from decimal import Decimal
from typing import Dict

from app.core.config import settings
from app.core.redis_client import redis_sync

# Redis key → settings attribute name
_RATE_MAP: Dict[str, str] = {
    "XOF": "fx_usd_to_xof",
    "XAF": "fx_usd_to_xaf",
    "GHS": "fx_usd_to_ghs",
    "NGN": "fx_usd_to_ngn",
    "KES": "fx_usd_to_kes",
    "EUR": "fx_usd_to_eur",
}

_REDIS_PREFIX = "config:fx_usd_to_"

# USD itself is always 1
_USD_RATE = Decimal("1")


def _redis_key(currency: str) -> str:
    return f"{_REDIS_PREFIX}{currency.lower()}"


def get_live_fx_rate() -> Decimal:
    """Return the active USD→XOF rate (backward-compat alias)."""
    return _get_rate("XOF")


def _get_rate(currency: str) -> Decimal:
    """Return 1 USD = X <currency> from Redis override or config default."""
    if currency == "USD":
        return _USD_RATE
    raw = redis_sync.get(_redis_key(currency))
    if raw:
        return Decimal(raw.decode() if isinstance(raw, bytes) else raw)
    attr = _RATE_MAP.get(currency.upper())
    if attr:
        return Decimal(str(getattr(settings, attr)))
    return _USD_RATE


def get_all_rates() -> Dict[str, Decimal]:
    """Return a dict of all supported 1-USD rates, including USD=1."""
    rates: Dict[str, Decimal] = {"USD": _USD_RATE}
    for currency in _RATE_MAP:
        rates[currency] = _get_rate(currency)
    return rates


def convert(amount: Decimal, from_currency: str, to_currency: str) -> Decimal:
    """Convert amount between any two supported currencies via USD pivot.

    Both currencies must be in the supported set (XOF, XAF, GHS, NGN, KES, EUR, USD).
    Returns amount expressed in to_currency.
    """
    fc = from_currency.upper()
    tc = to_currency.upper()
    if fc == tc:
        return amount
    rates = get_all_rates()
    rate_from = rates.get(fc, _USD_RATE)
    rate_to = rates.get(tc, _USD_RATE)
    # amount → USD → to_currency
    usd_amount = amount / rate_from
    return (usd_amount * rate_to).quantize(Decimal("0.01"))

"""
Runtime FX rate helper.

Priority: Redis override (set by admin) > settings default (FX_USD_TO_XOF env var).
Admin endpoint: PUT /admin/fx/rate {"rate": "655.957"}
"""

from decimal import Decimal

from app.core.config import settings
from app.core.redis_client import redis_sync

_REDIS_KEY = "config:fx_usd_to_xof"


def get_live_fx_rate() -> Decimal:
    """Return the active USD→XOF rate.

    Checks Redis first so an admin override via PUT /admin/fx/rate takes effect
    immediately without a service restart.
    """
    raw = redis_sync.get(_REDIS_KEY)
    if raw:
        return Decimal(raw.decode() if isinstance(raw, bytes) else raw)
    return Decimal(str(settings.fx_usd_to_xof))

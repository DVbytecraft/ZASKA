"""
Public FX rates endpoint — any authenticated user can fetch current rates.

GET  /fx/rates            → { base: "USD", rates: {...}, updated_at: "..." }
GET  /fx/convert?amount=&from=&to=  → { result, from_currency, to_currency }
"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user_id
from app.core.fx_rate import convert, get_all_rates
from app.core.responses import success_response

router = APIRouter(prefix="/fx", tags=["fx"])


@router.get("/rates")
def get_fx_rates(_: str = Depends(get_current_user_id)):
    """Return all current FX rates (1 USD = X currency).

    Rates are sourced from Redis admin overrides or config defaults.
    """
    rates = get_all_rates()
    return success_response({
        "base": "USD",
        "rates": {k: float(v) for k, v in rates.items()},
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })


@router.get("/convert")
def fx_convert(
    amount: str,
    from_currency: str,
    to_currency: str,
    _: str = Depends(get_current_user_id),
):
    """Convert an amount from one currency to another.

    Query params:
    - amount: decimal string (e.g. "5000")
    - from_currency: source currency code (XOF, USD, EUR…)
    - to_currency: target currency code
    """
    try:
        decimal_amount = Decimal(amount)
    except InvalidOperation:
        raise HTTPException(status_code=400, detail="Invalid amount — must be a valid decimal number")

    if decimal_amount < 0:
        raise HTTPException(status_code=400, detail="amount must be non-negative")

    fc = from_currency.upper()
    tc = to_currency.upper()

    supported = set(get_all_rates().keys())
    if fc not in supported:
        raise HTTPException(status_code=400, detail=f"Unsupported currency: {from_currency}. Supported: {sorted(supported)}")
    if tc not in supported:
        raise HTTPException(status_code=400, detail=f"Unsupported currency: {to_currency}. Supported: {sorted(supported)}")

    result = convert(decimal_amount, fc, tc)
    return success_response({
        "amount": str(decimal_amount),
        "from_currency": fc,
        "to_currency": tc,
        "result": float(result),
        "result_str": str(result),
    })

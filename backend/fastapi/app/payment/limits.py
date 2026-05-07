"""
Transaction limits and fraud detection for ZASKA PAY.

Redis-based daily counters for FX, deposits, and withdrawals.
All amounts are normalised to USD-equivalent for limit comparison.

Lua scripts guarantee atomic check-and-increment, eliminating TOCTOU races
between the GET (read current) and INCRBYFLOAT (apply delta).
"""

from __future__ import annotations

import time
from decimal import Decimal

from app.core.redis_client import redis_sync

_DAY_SECONDS = 86_400

# Atomic check-and-increment.
# Returns nil if limit would be exceeded; returns the new value string if OK.
# KEYS[1] = counter key
# ARGV[1] = amount to add (float string)
# ARGV[2] = max limit (float string)
# ARGV[3] = TTL seconds (0 = no expiry)
_LUA_CHECK_AND_INCREMENT = """
local current = tonumber(redis.call('GET', KEYS[1]) or '0') or 0
local amount = tonumber(ARGV[1])
local lim = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])
if current + amount > lim then
    return nil
end
local new_val = redis.call('INCRBYFLOAT', KEYS[1], amount)
if ttl > 0 and redis.call('TTL', KEYS[1]) < 0 then
    redis.call('EXPIRE', KEYS[1], ttl)
end
return new_val
"""


def _atomic_check_increment(
    key: str, amount_usd: Decimal, max_usd: Decimal, ttl_seconds: int
) -> bool:
    """Return True if increment succeeded; False if limit would be exceeded."""
    result = redis_sync.eval(
        _LUA_CHECK_AND_INCREMENT,
        1,
        key,
        f"{float(amount_usd):.8f}",
        f"{float(max_usd):.8f}",
        str(ttl_seconds),
    )
    return result is not None


class LimitExceeded(Exception):
    pass


class FraudDetected(Exception):
    pass


class TransactionLimits:
    """
    Enforces per-user daily limits and detects suspicious patterns via Redis counters.

    Keys use a 24-hour TTL and reset naturally — no cron needed.
    All amounts are normalised to USD for cross-currency comparisons.
    """

    def __init__(self, fx_rate_usd_to_xof: Decimal) -> None:
        self._fx_rate = fx_rate_usd_to_xof

    # ── Currency normalisation ─────────────────────────────────────────────────

    def _to_usd(self, amount: Decimal, currency: str) -> Decimal:
        cur = currency.upper()
        if cur == "USD":
            return amount
        if cur == "XOF":
            return (amount / self._fx_rate).quantize(Decimal("0.01"))
        return amount

    # ── FX limits ──────────────────────────────────────────────────────────────

    def check_fx_per_tx(
        self, *, user_id: str, amount: Decimal, currency: str, max_usd: Decimal
    ) -> None:
        amount_usd = self._to_usd(amount, currency)
        if amount_usd > max_usd:
            raise LimitExceeded(
                f"FX amount ${amount_usd:.2f} exceeds per-transaction limit ${max_usd:.2f}"
            )

    def check_and_record_fx_daily(
        self, *, user_id: str, amount: Decimal, currency: str, max_usd: Decimal
    ) -> None:
        amount_usd = self._to_usd(amount, currency)
        key = f"limit:fx_daily:{user_id}"
        if not _atomic_check_increment(key, amount_usd, max_usd, _DAY_SECONDS):
            current = Decimal(redis_sync.get(key) or "0")
            raise LimitExceeded(
                f"Daily FX limit ${max_usd:.2f} would be exceeded "
                f"(used: ${current:.2f}, requested: ${amount_usd:.2f})"
            )

    # ── Withdrawal limits ──────────────────────────────────────────────────────

    def check_and_record_withdrawal_daily(
        self, *, user_id: str, amount: Decimal, currency: str, max_usd: Decimal
    ) -> None:
        amount_usd = self._to_usd(amount, currency)
        key = f"limit:withdraw_daily:{user_id}"
        if not _atomic_check_increment(key, amount_usd, max_usd, _DAY_SECONDS):
            current = Decimal(redis_sync.get(key) or "0")
            raise LimitExceeded(
                f"Daily withdrawal limit ${max_usd:.2f} would be exceeded "
                f"(used: ${current:.2f}, requested: ${amount_usd:.2f})"
            )

    # ── Deposit limits ─────────────────────────────────────────────────────────

    def check_and_record_deposit_daily(
        self, *, user_id: str, amount: Decimal, currency: str, max_usd: Decimal
    ) -> None:
        amount_usd = self._to_usd(amount, currency)
        key = f"limit:deposit_daily:{user_id}"
        if not _atomic_check_increment(key, amount_usd, max_usd, _DAY_SECONDS):
            current = Decimal(redis_sync.get(key) or "0")
            raise LimitExceeded(
                f"Daily deposit limit ${max_usd:.2f} would be exceeded "
                f"(used: ${current:.2f}, requested: ${amount_usd:.2f})"
            )

    # ── Fraud detection ────────────────────────────────────────────────────────

    def record_deposit_timestamp(self, *, user_id: str) -> None:
        """Mark completion of a confirmed deposit for rapid-cycle detection.

        TTL must exceed the largest allowed rapid-cycle window (default 10 min but
        could be reconfigured).  We store for a full day so detection works even
        when the window_minutes setting is increased at runtime.
        """
        redis_sync.set(
            f"fraud:last_deposit:{user_id}",
            str(int(time.time())),
            ex=_DAY_SECONDS,
        )

    def check_rapid_cycle(self, *, user_id: str, window_minutes: int) -> None:
        """Raise FraudDetected if a deposit was completed within window_minutes."""
        raw = redis_sync.get(f"fraud:last_deposit:{user_id}")
        if raw:
            elapsed_seconds = int(time.time()) - int(raw)
            if elapsed_seconds < window_minutes * 60:
                remaining = window_minutes * 60 - elapsed_seconds
                raise FraudDetected(
                    f"Rapid deposit→withdrawal pattern detected "
                    f"(last deposit {elapsed_seconds}s ago). "
                    f"Please wait {remaining}s before withdrawing."
                )

    def record_payout_failure(self, *, user_id: str, threshold: int) -> None:
        """
        Increment consecutive-payout-failure counter.
        Raises FraudDetected once threshold is reached.
        """
        key = f"fraud:payout_fails:{user_id}"
        count = int(redis_sync.incr(key))
        if count == 1:
            redis_sync.expire(key, _DAY_SECONDS)
        if count >= threshold:
            raise FraudDetected(
                f"Account temporarily blocked: {count} consecutive payout failures. "
                "Contact support to unblock."
            )

    def clear_payout_failures(self, *, user_id: str) -> None:
        redis_sync.delete(f"fraud:payout_fails:{user_id}")

    # ── FX exposure (system-wide, not per-user) ────────────────────────────────

    def check_and_record_fx_exposure(
        self,
        *,
        direction: str,
        amount_usd: Decimal,
        limit_usd: Decimal,
    ) -> None:
        """
        direction = 'to_xof'   (USD → XOF: system sells XOF)
                  | 'from_xof' (XOF → USD: system buys XOF)

        Raises LimitExceeded if the running total would exceed limit_usd.
        Unlike daily limits, this counter has no TTL — it resets only via admin.
        """
        key = f"fx_exposure:{direction}"
        if not _atomic_check_increment(key, amount_usd, limit_usd, 0):
            current = Decimal(redis_sync.get(key) or "0")
            raise LimitExceeded(
                f"FX exposure limit ${limit_usd:.2f} exceeded "
                f"(direction={direction}, current=${current:.2f}, requested=${amount_usd:.2f}). "
                "Contact admin to reset."
            )

    def reset_fx_exposure(self, *, direction: str) -> None:
        """Admin-only: reset the FX exposure counter for a direction."""
        redis_sync.delete(f"fx_exposure:{direction}")

    def get_fx_exposure(self) -> dict[str, str]:
        """Return current FX exposure totals (admin/monitoring)."""
        return {
            "to_xof_usd": redis_sync.get("fx_exposure:to_xof") or "0",
            "from_xof_usd": redis_sync.get("fx_exposure:from_xof") or "0",
        }

    def get_daily_totals(self, *, user_id: str) -> dict[str, str]:
        """Return current daily usage for all limit buckets (for admin/debug)."""
        return {
            "fx_daily_usd": redis_sync.get(f"limit:fx_daily:{user_id}") or "0",
            "withdraw_daily_usd": redis_sync.get(f"limit:withdraw_daily:{user_id}") or "0",
            "deposit_daily_usd": redis_sync.get(f"limit:deposit_daily:{user_id}") or "0",
        }

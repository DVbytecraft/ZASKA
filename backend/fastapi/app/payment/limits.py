"""
Transaction limits and fraud detection for ZASKA PAY.

Redis-based daily counters for FX, deposits, and withdrawals.
All amounts are normalised to USD-equivalent for limit comparison.

Lua scripts guarantee atomic check-and-increment, eliminating TOCTOU races
between the GET (read current) and INCRBY* (apply delta).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from enum import Enum

from app.core.redis_client import redis_sync

_DAY_SECONDS = 86_400

# Atomic check-and-increment using integer math (no floats).
# Returns nil if limit would be exceeded; returns the new value string if OK.
# KEYS[1] = counter key
# ARGV[1] = amount delta (int as string, in cents)
# ARGV[2] = max limit (int as string, in cents)
# ARGV[3] = TTL seconds (0 = no expiry)
_LUA_CHECK_AND_INCREMENT = """
local current = tonumber(redis.call('GET', KEYS[1]) or '0') or 0
local amount = tonumber(ARGV[1])
local lim = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])

if current + amount > lim then
    return nil
end

local new_val = redis.call('INCRBY', KEYS[1], amount)
if ttl > 0 and redis.call('TTL', KEYS[1]) < 0 then
    redis.call('EXPIRE', KEYS[1], ttl)
end

return new_val
"""


def _atomic_check_increment(
    key: str, amount_usd: Decimal, max_usd: Decimal, ttl_seconds: int
) -> bool:
    """Return True if increment succeeded; False if limit would be exceeded.

    amount_usd/max_usd are expected to be in USD (Decimal). Internally we convert
    to integer cents for Redis atomic operations.
    """
    amount_cents = int(
        (amount_usd * 100).to_integral_value(rounding=ROUND_DOWN)
    )
    max_cents = int((max_usd * 100).to_integral_value(rounding=ROUND_DOWN))

    result = redis_sync.eval(
        _LUA_CHECK_AND_INCREMENT,
        1,
        key,
        str(amount_cents),
        str(max_cents),
        str(ttl_seconds),
    )
    return result is not None


class LimitExceeded(Exception):
    pass


class FraudDetected(Exception):
    pass


class DepositStatus(str, Enum):
    INITIATED = "initiated"
    PENDING_PROVIDER_CONFIRMATION = "pending_provider_confirmation"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"  # wallet credited
    FAILED = "failed"
    CANCELLED = "cancelled"


class WithdrawalStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class IdempotencyKey:
    """
    Deterministic idempotency key generator.

    Use it to enforce exactly-once semantics in your DB / webhook handler.

    The key should be based on:
    - user_id
    - operation scope (deposit/withdraw)
    - provider name
    - provider transaction id (or reference)
    """
    scope: str
    user_id: str
    provider: str
    provider_tx_id: str

    def redis_idempotency_key(self) -> str:
        # Optional integration: Redis-based dedupe for webhook retries.
        return (
            f"idemp:{self.scope}:{self.user_id}:"
            f"{self.provider}:{self.provider_tx_id}"
        )

    def ledger_reference(self) -> str:
        # Use this as Wallet ledger reference, and put UNIQUE(reference) on ledger table.
        safe_provider_tx = self.provider_tx_id.replace(":", "_").replace("/", "_")
        safe_provider = self.provider.replace(":", "_").replace("/", "_")
        return f"{self.scope}:{self.user_id}:{safe_provider}:{safe_provider_tx}"


def build_deposit_idempotency_key(
    *,
    user_id: str,
    provider: str,
    provider_tx_id: str,
) -> IdempotencyKey:
    return IdempotencyKey(
        scope="deposit",
        user_id=user_id,
        provider=provider,
        provider_tx_id=provider_tx_id,
    )


def build_withdrawal_idempotency_key(
    *,
    user_id: str,
    provider: str,
    provider_tx_id: str,
) -> IdempotencyKey:
    return IdempotencyKey(
        scope="withdraw",
        user_id=user_id,
        provider=provider,
        provider_tx_id=provider_tx_id,
    )


class InvalidStateTransition(Exception):
    pass


def transition_withdrawal(
    *,
    current: WithdrawalStatus,
    next_status: WithdrawalStatus,
    allow_from_terminal: bool = False,
) -> WithdrawalStatus:
    """
    Enforce a safe withdrawal state machine.

    Allowed transitions:
    - PENDING -> PROCESSING
    - PENDING -> FAILED
    - PROCESSING -> COMPLETED
    - PROCESSING -> FAILED
    """
    if (
        not allow_from_terminal
        and current in (WithdrawalStatus.COMPLETED, WithdrawalStatus.FAILED)
    ):
        raise InvalidStateTransition(
            f"Terminal state {current} cannot transition to {next_status}"
        )

    allowed: dict[WithdrawalStatus, set[WithdrawalStatus]] = {
        WithdrawalStatus.PENDING: {
            WithdrawalStatus.PROCESSING,
            WithdrawalStatus.FAILED,
        },
        WithdrawalStatus.PROCESSING: {
            WithdrawalStatus.COMPLETED,
            WithdrawalStatus.FAILED,
        },
    }

    if current not in allowed:
        raise InvalidStateTransition(f"Unknown current state {current}")

    if next_status not in allowed[current]:
        raise InvalidStateTransition(
            f"Invalid transition {current} -> {next_status}"
        )

    return next_status


def transition_deposit(
    *,
    current: DepositStatus,
    next_status: DepositStatus,
) -> DepositStatus:
    """
    Enforce deposit lifecycle transitions.

    Allowed transitions:
    - INITIATED -> PENDING_PROVIDER_CONFIRMATION | CANCELLED | FAILED
    - PENDING_PROVIDER_CONFIRMATION -> CONFIRMED | FAILED | CANCELLED
    - CONFIRMED -> COMPLETED | FAILED
    - COMPLETED, FAILED, CANCELLED are terminal.
    """
    terminal = {
        DepositStatus.COMPLETED,
        DepositStatus.FAILED,
        DepositStatus.CANCELLED,
    }
    if current in terminal:
        raise InvalidStateTransition(
            f"Terminal state {current} cannot transition to {next_status}"
        )

    allowed: dict[DepositStatus, set[DepositStatus]] = {
        DepositStatus.INITIATED: {
            DepositStatus.PENDING_PROVIDER_CONFIRMATION,
            DepositStatus.CANCELLED,
            DepositStatus.FAILED,
        },
        DepositStatus.PENDING_PROVIDER_CONFIRMATION: {
            DepositStatus.CONFIRMED,
            DepositStatus.FAILED,
            DepositStatus.CANCELLED,
        },
        DepositStatus.CONFIRMED: {
            DepositStatus.COMPLETED,
            DepositStatus.FAILED,
        },
    }

    if current not in allowed:
        raise InvalidStateTransition(f"Unknown current state {current}")

    if next_status not in allowed[current]:
        raise InvalidStateTransition(
            f"Invalid transition {current} -> {next_status}"
        )

    return next_status


def should_record_deposit_timestamp(*, next_deposit_status: DepositStatus) -> bool:
    """
    Record rapid-cycle fraud timestamp ONLY when funds are confirmed.
    """
    return next_deposit_status in {DepositStatus.CONFIRMED, DepositStatus.COMPLETED}


def record_deposit_timestamp_if_confirmed(
    *,
    limits: "TransactionLimits",
    user_id: str,
    next_deposit_status: DepositStatus,
) -> None:
    """
    Integration helper:
    - Call from webhook handler exactly once (or idempotently at ledger layer).
    - Rapid-cycle fraud should use confirmed lifecycle stage.
    """
    if should_record_deposit_timestamp(next_deposit_status=next_deposit_status):
        limits.record_deposit_timestamp(user_id=user_id)


class TransactionLimits:
    """
    Enforces per-user daily limits and detects suspicious patterns via Redis counters.

    Keys use a 24-hour TTL and reset naturally — no cron needed.
    All amounts are normalised to USD for cross-currency comparisons.

    Important:
    - This module uses integer cents for Redis limit enforcement to avoid float rounding drift.
    - FX normalization precision should be validated against get_live_fx_rate() contract.
    """

    def __init__(self, fx_rate_usd_to_xof: Decimal) -> None:
        self._fx_rate = fx_rate_usd_to_xof

    # ── Currency normalisation ──────────────────────────────────────────────

    def _to_usd(self, amount: Decimal, currency: str) -> Decimal:
        cur = currency.upper()
        if cur == "USD":
            return amount
        if cur == "XOF":
            # USD = XOF / fx_rate (only correct if fx_rate is 1 USD -> XOF).
            # Do NOT quantize here; quantize only when converting to cents in Redis.
            return amount / self._fx_rate
        return amount

    # ── FX limits ─────────────────────────────────────────────────────────────

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
            current = Decimal(redis_sync.get(key) or "0") / 100
            raise LimitExceeded(
                f"Daily FX limit ${max_usd:.2f} would be exceeded "
                f"(used: ${current:.2f}, requested: ${amount_usd:.2f})"
            )

    # ── Withdrawal limits ─────────────────────────────────────────────────────

    def check_and_record_withdrawal_daily(
        self, *, user_id: str, amount: Decimal, currency: str, max_usd: Decimal
    ) -> None:
        amount_usd = self._to_usd(amount, currency)
        key = f"limit:withdraw_daily:{user_id}"
        if not _atomic_check_increment(key, amount_usd, max_usd, _DAY_SECONDS):
            current = Decimal(redis_sync.get(key) or "0") / 100
            raise LimitExceeded(
                f"Daily withdrawal limit ${max_usd:.2f} would be exceeded "
                f"(used: ${current:.2f}, requested: ${amount_usd:.2f})"
            )

    # ── Deposit limits ────────────────────────────────────────────────────────

    def check_and_record_deposit_daily(
        self, *, user_id: str, amount: Decimal, currency: str, max_usd: Decimal
    ) -> None:
        amount_usd = self._to_usd(amount, currency)
        key = f"limit:deposit_daily:{user_id}"
        if not _atomic_check_increment(key, amount_usd, max_usd, _DAY_SECONDS):
            current = Decimal(redis_sync.get(key) or "0") / 100
            raise LimitExceeded(
                f"Daily deposit limit ${max_usd:.2f} would be exceeded "
                f"(used: ${current:.2f}, requested: ${amount_usd:.2f})"
            )

    # ── Fraud detection ────────────────────────────────────────────────────────

    def record_deposit_timestamp(self, *, user_id: str) -> None:
        """Mark completion of a confirmed deposit for rapid-cycle detection."""
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
        """Increment consecutive-payout-failure counter."""
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

        Unlike daily limits, this counter has no TTL — it resets only via admin.
        """
        key = f"fx_exposure:{direction}"
        if not _atomic_check_increment(key, amount_usd, limit_usd, 0):
            current = Decimal(redis_sync.get(key) or "0") / 100
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
            "to_xof_usd": str(
                Decimal(redis_sync.get("fx_exposure:to_xof") or "0") / 100
            ),
            "from_xof_usd": str(
                Decimal(redis_sync.get("fx_exposure:from_xof") or "0") / 100
            ),
        }

    def get_daily_totals(self, *, user_id: str) -> dict[str, str]:
        """Return current daily usage for all limit buckets (for admin/debug)."""
        return {
            "fx_daily_usd": str(
                Decimal(redis_sync.get(f"limit:fx_daily:{user_id}") or "0") / 100
            ),
            "withdraw_daily_usd": str(
                Decimal(redis_sync.get(f"limit:withdraw_daily:{user_id}") or "0") / 100
            ),
            "deposit_daily_usd": str(
                Decimal(redis_sync.get(f"limit:deposit_daily:{user_id}") or "0") / 100
            ),
        }

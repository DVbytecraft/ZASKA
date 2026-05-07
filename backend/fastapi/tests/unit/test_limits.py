"""Tests pour les limites de transactions et détection de fraude."""
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
import time


class TestTransactionLimits:
    def _make_limits(self):
        from app.payment.limits import TransactionLimits

        return TransactionLimits(fx_rate_usd_to_xof=Decimal("620"))

    def test_fx_per_tx_ok(self):
        limits = self._make_limits()
        # check_fx_per_tx does not use Redis — no mock needed
        limits.check_fx_per_tx(
            user_id="user1",
            amount=Decimal("100"),
            currency="USD",
            max_usd=Decimal("1000"),
        )

    def test_fx_per_tx_exceeded(self):
        from app.payment.limits import LimitExceeded

        limits = self._make_limits()
        with pytest.raises(LimitExceeded):
            limits.check_fx_per_tx(
                user_id="user1",
                amount=Decimal("2000"),
                currency="USD",
                max_usd=Decimal("1000"),
            )

    def test_check_and_record_fx_daily_ok(self):
        """Lua eval returning non-None means limit was not exceeded."""
        limits = self._make_limits()
        with patch("app.payment.limits.redis_sync") as mock_redis:
            mock_redis.eval.return_value = b"50.00"  # Lua returns new value as bytes
            limits.check_and_record_fx_daily(
                user_id="user1",
                amount=Decimal("50"),
                currency="USD",
                max_usd=Decimal("1000"),
            )
            mock_redis.eval.assert_called_once()

    def test_check_and_record_fx_daily_exceeded(self):
        """Lua eval returning None means limit would be exceeded."""
        from app.payment.limits import LimitExceeded

        limits = self._make_limits()
        with patch("app.payment.limits.redis_sync") as mock_redis:
            mock_redis.eval.return_value = None  # Lua returns nil
            mock_redis.get.return_value = "950.00"  # current usage for error msg
            with pytest.raises(LimitExceeded, match="Daily FX limit"):
                limits.check_and_record_fx_daily(
                    user_id="user1",
                    amount=Decimal("100"),
                    currency="USD",
                    max_usd=Decimal("1000"),
                )

    def test_check_and_record_withdrawal_daily_ok(self):
        limits = self._make_limits()
        with patch("app.payment.limits.redis_sync") as mock_redis:
            mock_redis.eval.return_value = b"200.00"
            limits.check_and_record_withdrawal_daily(
                user_id="user1",
                amount=Decimal("200"),
                currency="USD",
                max_usd=Decimal("500"),
            )

    def test_check_and_record_withdrawal_daily_exceeded(self):
        from app.payment.limits import LimitExceeded

        limits = self._make_limits()
        with patch("app.payment.limits.redis_sync") as mock_redis:
            mock_redis.eval.return_value = None
            mock_redis.get.return_value = "490.00"
            with pytest.raises(LimitExceeded, match="Daily withdrawal limit"):
                limits.check_and_record_withdrawal_daily(
                    user_id="user1",
                    amount=Decimal("50"),
                    currency="USD",
                    max_usd=Decimal("500"),
                )

    def test_check_and_record_deposit_daily_ok(self):
        limits = self._make_limits()
        with patch("app.payment.limits.redis_sync") as mock_redis:
            mock_redis.eval.return_value = b"100.00"
            limits.check_and_record_deposit_daily(
                user_id="user1",
                amount=Decimal("100"),
                currency="USD",
                max_usd=Decimal("2000"),
            )

    def test_fx_exposure_ok(self):
        limits = self._make_limits()
        with patch("app.payment.limits.redis_sync") as mock_redis:
            mock_redis.eval.return_value = b"5000.00"
            limits.check_and_record_fx_exposure(
                direction="to_xof",
                amount_usd=Decimal("5000"),
                limit_usd=Decimal("100000"),
            )

    def test_fx_exposure_exceeded(self):
        from app.payment.limits import LimitExceeded

        limits = self._make_limits()
        with patch("app.payment.limits.redis_sync") as mock_redis:
            mock_redis.eval.return_value = None
            mock_redis.get.return_value = "99000.00"
            with pytest.raises(LimitExceeded, match="FX exposure limit"):
                limits.check_and_record_fx_exposure(
                    direction="to_xof",
                    amount_usd=Decimal("2000"),
                    limit_usd=Decimal("100000"),
                )

    def test_rapid_cycle_detection(self):
        from app.payment.limits import FraudDetected

        limits = self._make_limits()
        with patch("app.payment.limits.redis_sync") as mock_redis:
            mock_redis.get.return_value = str(int(time.time()) - 30)  # 30s ago
            with pytest.raises(FraudDetected):
                limits.check_rapid_cycle(user_id="user1", window_minutes=10)

    def test_rapid_cycle_ok_after_window(self):
        limits = self._make_limits()
        with patch("app.payment.limits.redis_sync") as mock_redis:
            mock_redis.get.return_value = str(int(time.time()) - 700)  # 700s ago > 10min
            limits.check_rapid_cycle(user_id="user1", window_minutes=10)  # should not raise

    def test_xof_converted_to_usd(self):
        """XOF amounts are normalised before checking against USD limits."""
        limits = self._make_limits()
        with patch("app.payment.limits.redis_sync") as mock_redis:
            mock_redis.eval.return_value = None
            mock_redis.get.return_value = "0"
            from app.payment.limits import LimitExceeded
            # 620,000 XOF / 620 = $1,000 USD — exactly at limit
            with pytest.raises(LimitExceeded):
                limits.check_and_record_deposit_daily(
                    user_id="user1",
                    amount=Decimal("620001"),
                    currency="XOF",
                    max_usd=Decimal("1000"),
                )

    def test_payout_failure_blocks_at_threshold(self):
        from app.payment.limits import FraudDetected

        limits = self._make_limits()
        with patch("app.payment.limits.redis_sync") as mock_redis:
            mock_redis.incr.return_value = 3
            mock_redis.expire.return_value = True
            with pytest.raises(FraudDetected, match="consecutive payout failures"):
                limits.record_payout_failure(user_id="user1", threshold=3)

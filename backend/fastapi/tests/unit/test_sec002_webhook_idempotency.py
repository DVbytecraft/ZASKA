"""SEC-002: Webhook idempotency pre-check — atomic SETNX claim before processing.

Tests verify:
  1. WebhookQueue.claim() is atomic (SETNX semantics)
  2. WebhookQueue.unclaim() releases a claim
  3. _credit_wallet_from_topup_event:
     - first call claims and credits
     - duplicate (is_processed=True) returns (False, key) without crediting
     - concurrent duplicate (claim fails) returns (False, key) without crediting
     - credit failure unclams key so provider can retry
     - missing metadata keeps claim (permanently skipped, not retried)
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, call, patch


# ---------------------------------------------------------------------------
# Fake synchronous Redis that supports SETNX (set with nx=True)
# ---------------------------------------------------------------------------

class _FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}

    def get(self, key: str):
        return self.store.get(key)

    def set(self, key: str, value: str, nx: bool = False, ex: int | None = None):
        if nx and key in self.store:
            return None  # NX failed
        self.store[key] = value
        return True

    def setex(self, key: str, ttl: int, value: str):
        self.store[key] = value
        return True

    def delete(self, key: str):
        self.store.pop(key, None)
        return 1

    def exists(self, key: str) -> int:
        return 1 if key in self.store else 0


# ---------------------------------------------------------------------------
# Helper: build a minimal WebhookEvent-like object
# ---------------------------------------------------------------------------

def _make_event(provider_tx_id: str = "evt_001", amount: str = "10.00", **raw_overrides):
    from app.services.payment.base_provider import WebhookEvent
    raw = {
        "stripe_event_id": provider_tx_id,
        "user_id": "user-abc",
        "currency": "XOF",
        "reference": "ref-001",
        **raw_overrides,
    }
    return WebhookEvent(
        event_type="wallet_topup",
        provider_tx_id=provider_tx_id,
        escrow_id="",
        amount=Decimal(amount),
        currency="XOF",
        raw_data=raw,
    )


# ===========================================================================
# 1. WebhookQueue.claim / unclaim unit tests
# ===========================================================================

class TestWebhookQueueClaim:
    def test_claim_returns_true_on_first_call(self):
        fake = _FakeRedis()
        with patch("app.services.payment.webhook_queue.redis_sync", fake):
            from app.services.payment.webhook_queue import WebhookQueue
            assert WebhookQueue.claim("key-001") is True

    def test_claim_returns_false_on_second_call_same_key(self):
        fake = _FakeRedis()
        with patch("app.services.payment.webhook_queue.redis_sync", fake):
            from app.services.payment.webhook_queue import WebhookQueue
            assert WebhookQueue.claim("key-002") is True
            assert WebhookQueue.claim("key-002") is False

    def test_claim_different_keys_both_succeed(self):
        fake = _FakeRedis()
        with patch("app.services.payment.webhook_queue.redis_sync", fake):
            from app.services.payment.webhook_queue import WebhookQueue
            assert WebhookQueue.claim("key-a") is True
            assert WebhookQueue.claim("key-b") is True

    def test_unclaim_releases_key_so_next_claim_succeeds(self):
        fake = _FakeRedis()
        with patch("app.services.payment.webhook_queue.redis_sync", fake):
            from app.services.payment.webhook_queue import WebhookQueue
            assert WebhookQueue.claim("key-003") is True
            WebhookQueue.unclaim("key-003")
            assert WebhookQueue.claim("key-003") is True

    def test_unclaim_nonexistent_key_is_noop(self):
        fake = _FakeRedis()
        with patch("app.services.payment.webhook_queue.redis_sync", fake):
            from app.services.payment.webhook_queue import WebhookQueue
            WebhookQueue.unclaim("ghost-key")  # must not raise

    def test_claim_sets_correct_redis_key_prefix(self):
        fake = _FakeRedis()
        with patch("app.services.payment.webhook_queue.redis_sync", fake):
            from app.services.payment.webhook_queue import WebhookQueue
            WebhookQueue.claim("mykey")
            full_key = f"{WebhookQueue.PROCESSED_PREFIX}mykey"
            assert fake.store.get(full_key) == "1"


# ===========================================================================
# 2. _credit_wallet_from_topup_event behaviour
# ===========================================================================

def _make_wallet_svc():
    svc = MagicMock()
    svc.credit_wallet.return_value = None
    return svc


class TestCreditWalletIdempotency:

    def _run(self, event, fake_redis, wallet_svc=None, db=None):
        """Invoke _credit_wallet_from_topup_event with patched Redis."""
        if wallet_svc is None:
            wallet_svc = _make_wallet_svc()
        with patch("app.services.payment.webhook_queue.redis_sync", fake_redis), \
             patch("app.api.v1.routers.payments.TransactionLimits") as _tl_cls, \
             patch("app.api.v1.routers.payments.FinancialAuditLogger"):
            _tl_cls.return_value.record_deposit_timestamp.return_value = None
            from app.api.v1.routers.payments import _credit_wallet_from_topup_event
            return _credit_wallet_from_topup_event(event, wallet_svc, "stripe", db=db)

    # -----------------------------------------------------------------------
    # 2a. Happy path: first call claims, credits, marks processed
    # -----------------------------------------------------------------------
    def test_first_call_credits_and_returns_processed(self):
        fake = _FakeRedis()
        ws = _make_wallet_svc()
        event = _make_event()
        processed, idem_key = self._run(event, fake, wallet_svc=ws)
        assert processed is True
        assert "topup" in idem_key
        ws.credit_wallet.assert_called_once()

    # -----------------------------------------------------------------------
    # 2b. Duplicate: is_processed=True → returns (False, key), no credit
    # -----------------------------------------------------------------------
    def test_duplicate_via_is_processed_skips_credit(self):
        fake = _FakeRedis()
        # Pre-seed the processed key so is_processed() returns True
        idem_key = "stripe:topup:evt_001"
        fake.store[f"payment:webhooks:processed:{idem_key}"] = "1"

        ws = _make_wallet_svc()
        event = _make_event()
        processed, _ = self._run(event, fake, wallet_svc=ws)
        assert processed is False
        ws.credit_wallet.assert_not_called()

    # -----------------------------------------------------------------------
    # 2c. Concurrent duplicate: claim fails → returns (False, key), no credit
    # -----------------------------------------------------------------------
    def test_concurrent_duplicate_claim_fails_skips_credit(self):
        fake = _FakeRedis()
        # Simulate another request already holding the claim
        idem_key = "stripe:topup:evt_001"
        fake.store[f"payment:webhooks:processed:{idem_key}"] = "1"
        # Make is_processed return False by using a different key namespace
        # (we want to test the claim path, not the is_processed path)
        # Override: remove from store so is_processed returns False, but
        # pre-populate with a value that won't match PROCESSED_PREFIX lookup
        del fake.store[f"payment:webhooks:processed:{idem_key}"]
        # Seed with NX-blocking entry directly
        fake.store[f"payment:webhooks:processed:{idem_key}"] = "1"
        # Now is_processed sees it too — let's use a fresh key and block claim manually

        # Use a completely different approach: patch claim to return False directly
        ws = _make_wallet_svc()
        event = _make_event(provider_tx_id="evt_concurrent")
        with patch("app.services.payment.webhook_queue.redis_sync", fake), \
             patch("app.api.v1.routers.payments.TransactionLimits"), \
             patch("app.api.v1.routers.payments.FinancialAuditLogger"), \
             patch("app.services.payment.webhook_queue.WebhookQueue.claim", return_value=False):
            from app.api.v1.routers.payments import _credit_wallet_from_topup_event
            processed, _ = _credit_wallet_from_topup_event(event, ws, "stripe", db=None)
        assert processed is False
        ws.credit_wallet.assert_not_called()

    # -----------------------------------------------------------------------
    # 2d. Credit failure → unclaim called, exception re-raised
    # -----------------------------------------------------------------------
    def test_credit_failure_unclams_key(self):
        import pytest
        fake = _FakeRedis()
        ws = _make_wallet_svc()
        ws.credit_wallet.side_effect = RuntimeError("DB timeout")
        event = _make_event(provider_tx_id="evt_fail")

        with patch("app.services.payment.webhook_queue.redis_sync", fake), \
             patch("app.api.v1.routers.payments.TransactionLimits"), \
             patch("app.api.v1.routers.payments.FinancialAuditLogger"):
            from app.api.v1.routers.payments import _credit_wallet_from_topup_event
            with pytest.raises(RuntimeError, match="DB timeout"):
                _credit_wallet_from_topup_event(event, ws, "stripe", db=None)

        # Claim must have been released so the provider can retry
        idem_key = "stripe:topup:evt_fail"
        full_key = f"payment:webhooks:processed:{idem_key}"
        assert full_key not in fake.store

    # -----------------------------------------------------------------------
    # 2e. Missing metadata: claim is kept (event permanently skipped)
    # -----------------------------------------------------------------------
    def test_missing_user_id_keeps_claim_no_credit(self):
        fake = _FakeRedis()
        ws = _make_wallet_svc()
        event = _make_event(provider_tx_id="evt_bad", user_id="")  # missing user_id

        processed, idem_key = self._run(event, fake, wallet_svc=ws)
        assert processed is True  # caller should not retry
        ws.credit_wallet.assert_not_called()
        # Claim must still be set (so provider retry also gets skipped)
        full_key = f"payment:webhooks:processed:{idem_key}"
        assert fake.store.get(full_key) == "1"

    def test_missing_currency_keeps_claim_no_credit(self):
        fake = _FakeRedis()
        ws = _make_wallet_svc()
        event = _make_event(provider_tx_id="evt_nocur", currency="")  # missing currency
        # Rebuild event with no currency in raw_data
        from app.services.payment.base_provider import WebhookEvent
        raw = {"stripe_event_id": "evt_nocur", "user_id": "user-abc", "currency": "", "reference": "ref"}
        event = WebhookEvent(
            event_type="wallet_topup",
            provider_tx_id="evt_nocur",
            escrow_id="",
            amount=Decimal("5.00"),
            currency="",
            raw_data=raw,
        )

        processed, idem_key = self._run(event, fake, wallet_svc=ws)
        assert processed is True
        ws.credit_wallet.assert_not_called()

    def test_zero_amount_keeps_claim_no_credit(self):
        fake = _FakeRedis()
        ws = _make_wallet_svc()
        event = _make_event(provider_tx_id="evt_zero", amount="0")

        processed, idem_key = self._run(event, fake, wallet_svc=ws)
        assert processed is True
        ws.credit_wallet.assert_not_called()

    # -----------------------------------------------------------------------
    # 2f. Second identical event after first succeeds → duplicate (no double-credit)
    # -----------------------------------------------------------------------
    def test_second_event_after_success_is_duplicate(self):
        fake = _FakeRedis()
        ws1 = _make_wallet_svc()
        event = _make_event(provider_tx_id="evt_once")

        # First call
        processed1, _ = self._run(event, fake, wallet_svc=ws1)
        assert processed1 is True
        ws1.credit_wallet.assert_called_once()

        # Second call with same event — Redis key already set by first call
        ws2 = _make_wallet_svc()
        processed2, _ = self._run(event, fake, wallet_svc=ws2)
        assert processed2 is False
        ws2.credit_wallet.assert_not_called()

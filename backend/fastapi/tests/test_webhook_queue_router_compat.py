import json

import pytest
from fastapi import Request

from app.api.v1.routers import payments
from app.services.payment.base_provider import WebhookEvent


class DummyRequest:
    def __init__(self, body: bytes, headers: dict[str, str] | None = None):
        self._body = body
        self.headers = headers or {}

    async def body(self):
        return self._body


class DummyProvider:
    async def verify_webhook(self, raw_body: bytes, headers: dict[str, str]):
        return WebhookEvent(
            event_type="payment.success",
            provider_tx_id="tx_123",
            escrow_id="esc_123",
            amount=0,
            currency="XOF",
            raw_data={},
        )


@pytest.mark.asyncio
async def test_handle_webhook_does_not_mutate_wallet(monkeypatch):
    calls = {"success": 0, "failure": 0, "finalize": 0}

    class DummyWallet:
        def finalize_transaction(self, *_args, **_kwargs):
            calls["finalize"] += 1

    provider = DummyProvider()
    event = await payments._handle_webhook(provider, b"{}", {}, DummyWallet())

    assert event.provider_tx_id == "tx_123"
    assert calls["finalize"] == 0


@pytest.mark.asyncio
async def test_webhook_endpoint_enqueues_only(monkeypatch):
    queued = {}

    class FakeStripe:
        async def verify_webhook(self, *_args, **_kwargs):
            return WebhookEvent(
                event_type="payment.success",
                provider_tx_id="pi_1",
                escrow_id="esc_1",
                amount=0,
                currency="EUR",
                raw_data={},
            )

    def fake_enqueue(event):
        queued["event"] = event

    monkeypatch.setattr(payments, "StripeProvider", FakeStripe)
    monkeypatch.setattr(payments.WebhookQueue, "enqueue", fake_enqueue)

    req = DummyRequest(b'{"id":"evt"}', {"x-request-id": "req-1"})
    out = await payments.webhook_stripe(req, db=None)

    assert out == {"received": True}
    assert queued["event"].provider == "stripe"
    assert queued["event"].idempotency_key == "stripe:pi_1"

"""
Unit tests for wallet topup webhook ordering.

Verifies that credit_wallet is called BEFORE mark_processed:
- If credit fails → webhook is not marked → provider can retry safely
- If credit succeeds → webhook is marked → no double-credit on retry
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, call, patch

import pytest

from app.services.payment.webhook_queue import WebhookQueue
from app.services.payment import WebhookEvent


def _make_event(amount: Decimal = Decimal("100"), user_id: str = "user-a") -> WebhookEvent:
    return WebhookEvent(
        event_type="wallet_topup",
        provider_tx_id="evt_test_001",
        escrow_id=None,
        amount=amount,
        currency="USD",
        raw_data={
            "user_id": user_id,
            "currency": "USD",
            "reference": "ref_001",
            "stripe_event_id": "evt_test_001",
        },
    )


@pytest.fixture()
def mock_wallet_svc():
    svc = MagicMock()
    svc.credit_wallet.return_value = MagicMock()
    return svc


def test_credit_called_before_mark_processed(mock_wallet_svc):
    """credit_wallet must be called before mark_processed."""
    call_order: list[str] = []

    mock_wallet_svc.credit_wallet.side_effect = lambda **kw: call_order.append("credit")
    with (
        patch.object(WebhookQueue, "is_processed", return_value=False),
        patch.object(WebhookQueue, "claim", return_value=True),
        patch.object(WebhookQueue, "mark_processed", side_effect=lambda *a, **kw: call_order.append("mark")),
        patch("app.payment.limits.TransactionLimits.record_deposit_timestamp"),
        patch("app.payment.audit_logger.FinancialAuditLogger.log"),
    ):
        from app.api.v1.routers.payments import _credit_wallet_from_topup_event
        _credit_wallet_from_topup_event(_make_event(), mock_wallet_svc, "stripe", db=None)

    assert call_order == ["credit", "mark"], (
        f"Expected credit→mark order, got: {call_order}. "
        "Reversing order would lose user funds on crash."
    )


def test_idempotent_skips_already_processed(mock_wallet_svc):
    """A processed event must not trigger a second credit."""
    with patch.object(WebhookQueue, "is_processed", return_value=True):
        from app.api.v1.routers.payments import _credit_wallet_from_topup_event
        processed, _ = _credit_wallet_from_topup_event(_make_event(), mock_wallet_svc, "stripe", db=None)

    assert processed is False
    mock_wallet_svc.credit_wallet.assert_not_called()


def test_missing_metadata_skips_credit_without_error(mock_wallet_svc):
    """Events with missing user_id/currency must be skipped gracefully."""
    bad_event = WebhookEvent(
        event_type="wallet_topup",
        provider_tx_id="evt_bad",
        escrow_id=None,
        amount=Decimal("50"),
        currency="USD",
        raw_data={"stripe_event_id": "evt_bad"},  # no user_id or currency
    )
    with (
        patch.object(WebhookQueue, "is_processed", return_value=False),
        patch.object(WebhookQueue, "claim", return_value=True),
        patch.object(WebhookQueue, "mark_processed"),
    ):
        from app.api.v1.routers.payments import _credit_wallet_from_topup_event
        processed, _ = _credit_wallet_from_topup_event(bad_event, mock_wallet_svc, "stripe", db=None)

    assert processed is True  # not a duplicate, just skipped
    mock_wallet_svc.credit_wallet.assert_not_called()

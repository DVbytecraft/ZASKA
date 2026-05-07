from decimal import Decimal

import pytest

from app.payment.providers.mock_provider import MockPaymentProvider


@pytest.mark.asyncio
async def test_mock_provider_create_payment_returns_local_result():
    provider = MockPaymentProvider()
    result = await provider.create_payment(
        amount=Decimal("1200"),
        currency="XOF",
        user_id="u1",
        user_email="u1@test.com",
        metadata={"task_id": "t1"},
        idempotency_key="idem-1",
    )
    assert result.provider == "mock"
    assert result.status == "created"
    assert result.amount == Decimal("1200")

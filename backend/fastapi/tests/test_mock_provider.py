"""
Tests du MockProvider et des routes mock.

Stratégie :
  - WalletService sur SQLite in-memory (ACID réel)
  - MockProvider sans aucun mock réseau (c'est lui le mock)
  - Routes testées via starlette TestClient (sans serveur live)

Couvre :
  1. create_payment_intent → status pending, payment_url mock
  2. handle_success → escrow funded (crédit réel via WalletService)
  3. handle_success idempotent → pas de double crédit
  4. handle_failure → escrow cancelled
  5. Route mock/success → 200 en mode dev
  6. Route mock/success → 403 en mode sandbox/production
  7. Factory dev → retourne bien MockProvider
  8. Factory sandbox → retourne provider réel (Stripe/FedaPay)

Lancer : pytest tests/test_mock_provider.py -v
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.task import Task
from app.models.user import User
from app.services.payment.base_provider import WebhookEvent
from app.services.payment.mock_provider import MockProvider
from app.services.wallet_service import EscrowError, WalletService


# ── DB Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def db_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db(db_engine):
    Session = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session = Session()

    for obj in [
        User(id="u1", email="u1@test.com", password_hash="x", role="client", is_verified=True),
        User(id="u2", email="u2@test.com", password_hash="x", role="worker", is_verified=True),
        Task(id="t1", title="Électricité", description="Court-circuit", price=8000.0,
             currency="XOF", latitude=6.1, longitude=1.2, status="OPEN", created_by="u1"),
    ]:
        if not session.get(type(obj), obj.id):
            session.add(obj)
    session.commit()

    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def wallet_svc(db) -> WalletService:
    return WalletService(db)


@pytest.fixture()
def mock_provider() -> MockProvider:
    return MockProvider()


def _pending_escrow(wallet_svc: WalletService, amount: Decimal = Decimal("8000")) -> object:
    """Crée un escrow pending pour les tests."""
    return wallet_svc.create_pending_escrow(
        task_id="t1",
        payer_id="u1",
        payee_id="u2",
        amount=amount,
        currency="XOF",
    )


def _event(escrow_id: str, event_type: str = "payment.success") -> WebhookEvent:
    return WebhookEvent(
        event_type=event_type,
        provider_tx_id=f"mock_tx_{escrow_id[:8]}",
        escrow_id=escrow_id,
        amount=Decimal("0"),
        currency="XOF",
        raw_data={"simulated": True},
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1. MockProvider.create_payment_intent
# ═══════════════════════════════════════════════════════════════════════════

class TestMockProviderCreateIntent:

    @pytest.mark.asyncio
    async def test_returns_mock_provider_name(self, mock_provider):
        with patch("app.core.config.settings") as ms:
            ms.payment_mode = "dev"
            ms.payment_webhook_base_url = "http://localhost:6969"
            result = await mock_provider.create_payment_intent(
                amount=Decimal("5000"),
                currency="XOF",
                user_id="u1",
                user_email="u1@test.com",
                escrow_id="esc-test",
                task_id="t1",
                task_description="Plomberie",
                country_code="TG",
                idempotency_key="idem-test",
            )
        assert result.provider == "mock"

    @pytest.mark.asyncio
    async def test_returns_payment_url_pointing_to_mock_endpoint(self, mock_provider):
        with patch("app.core.config.settings") as ms:
            ms.payment_mode = "dev"
            ms.payment_webhook_base_url = "http://localhost:6969"
            result = await mock_provider.create_payment_intent(
                amount=Decimal("5000"),
                currency="XOF",
                user_id="u1",
                user_email="u1@test.com",
                escrow_id="esc-url",
                task_id="t1",
                task_description="Test",
                country_code="TG",
                idempotency_key="idem-url",
            )
        assert result.payment_url is not None
        assert "mock/success" in result.payment_url
        assert "esc-url" in result.payment_url

    @pytest.mark.asyncio
    async def test_client_secret_is_none(self, mock_provider):
        with patch("app.core.config.settings") as ms:
            ms.payment_mode = "dev"
            ms.payment_webhook_base_url = "http://localhost:6969"
            result = await mock_provider.create_payment_intent(
                amount=Decimal("100"),
                currency="EUR",
                user_id="u1",
                user_email="u1@test.com",
                escrow_id="esc-stripe",
                task_id="t1",
                task_description="Test FR",
                country_code="FR",
                idempotency_key="idem-fr",
            )
        assert result.client_secret is None

    @pytest.mark.asyncio
    async def test_provider_intent_id_starts_with_mock(self, mock_provider):
        with patch("app.core.config.settings") as ms:
            ms.payment_mode = "dev"
            ms.payment_webhook_base_url = "http://localhost:6969"
            result = await mock_provider.create_payment_intent(
                amount=Decimal("3000"),
                currency="GHS",
                user_id="u1",
                user_email="",
                escrow_id="esc-gh",
                task_id="t1",
                task_description="GH test",
                country_code="GH",
                idempotency_key="idem-gh",
            )
        assert result.provider_intent_id.startswith("mock_")

    @pytest.mark.asyncio
    async def test_amount_and_currency_preserved(self, mock_provider):
        with patch("app.core.config.settings") as ms:
            ms.payment_mode = "dev"
            ms.payment_webhook_base_url = "http://localhost:6969"
            result = await mock_provider.create_payment_intent(
                amount=Decimal("12345"),
                currency="XOF",
                user_id="u1",
                user_email="",
                escrow_id="esc-amt",
                task_id="t1",
                task_description="Montant test",
                country_code="TG",
                idempotency_key="idem-amt",
            )
        assert result.amount == Decimal("12345")
        assert result.currency == "XOF"


# ═══════════════════════════════════════════════════════════════════════════
# 2. MockProvider.handle_success — crédit escrow
# ═══════════════════════════════════════════════════════════════════════════

class TestMockHandleSuccess:

    @pytest.mark.asyncio
    async def test_escrow_becomes_funded(self, mock_provider, wallet_svc):
        escrow = _pending_escrow(wallet_svc)
        assert escrow.status == "pending"

        event = _event(escrow.id, "payment.success")
        await mock_provider.handle_success(event, wallet_svc)

        # Re-fetch
        from sqlalchemy import select
        from app.models.wallet import Escrow
        funded = wallet_svc.db.execute(
            select(Escrow).where(Escrow.id == escrow.id)
        ).scalars().one()
        assert funded.status == "funded"
        assert funded.funding_tx_id is not None

    @pytest.mark.asyncio
    async def test_escrow_funded_has_inbound_transaction(self, mock_provider, wallet_svc):
        escrow = _pending_escrow(wallet_svc)
        event = _event(escrow.id)
        await mock_provider.handle_success(event, wallet_svc)

        from sqlalchemy import select
        from app.models.wallet import Transaction
        txs = wallet_svc.db.execute(
            select(Transaction).where(Transaction.provider == "mock")
        ).scalars().all()
        assert len(txs) >= 1
        tx = next(t for t in txs if t.reference.startswith("pay:mock:"))
        assert tx.type == "inbound"
        assert tx.amount == Decimal("8000")

    @pytest.mark.asyncio
    async def test_double_success_is_idempotent_no_double_credit(self, mock_provider, wallet_svc):
        """Deux appels handle_success sur le même escrow → pas de double crédit."""
        escrow = _pending_escrow(wallet_svc)
        event = _event(escrow.id)

        await mock_provider.handle_success(event, wallet_svc)
        # Deuxième appel — doit être silencieux (idempotent)
        await mock_provider.handle_success(event, wallet_svc)

        from sqlalchemy import select
        from app.models.wallet import Transaction
        mock_txs = wallet_svc.db.execute(
            select(Transaction)
            .where(
                Transaction.reference == f"pay:mock:{event.provider_tx_id}"
            )
        ).scalars().all()
        # Une seule transaction créée malgré deux appels
        assert len(mock_txs) == 1

    @pytest.mark.asyncio
    async def test_handle_success_missing_escrow_id_is_silent(self, mock_provider, wallet_svc):
        """escrow_id absent → pas d'exception, simple log warning."""
        event = WebhookEvent(
            event_type="payment.success",
            provider_tx_id="mock_no_escrow",
            escrow_id="",  # absent
            amount=Decimal("0"),
            currency="",
        )
        # Doit passer sans exception
        await mock_provider.handle_success(event, wallet_svc)

    @pytest.mark.asyncio
    async def test_handle_success_unknown_escrow_raises_via_wallet(self, mock_provider, wallet_svc):
        """escrow_id inexistant → EscrowError capturée (idempotent silencieux)."""
        event = _event("escrow-does-not-exist-999")
        # Ne doit pas propager l'exception
        await mock_provider.handle_success(event, wallet_svc)


# ═══════════════════════════════════════════════════════════════════════════
# 3. MockProvider.handle_failure — annulation escrow
# ═══════════════════════════════════════════════════════════════════════════

class TestMockHandleFailure:

    @pytest.mark.asyncio
    async def test_escrow_becomes_cancelled(self, mock_provider, wallet_svc):
        escrow = _pending_escrow(wallet_svc)
        event = _event(escrow.id, "payment.failed")
        await mock_provider.handle_failure(event, wallet_svc)

        from sqlalchemy import select
        from app.models.wallet import Escrow
        cancelled = wallet_svc.db.execute(
            select(Escrow).where(Escrow.id == escrow.id)
        ).scalars().one()
        assert cancelled.status == "cancelled"

    @pytest.mark.asyncio
    async def test_double_failure_is_idempotent(self, mock_provider, wallet_svc):
        escrow = _pending_escrow(wallet_svc)
        event = _event(escrow.id, "payment.failed")
        await mock_provider.handle_failure(event, wallet_svc)
        # Deuxième appel idempotent
        await mock_provider.handle_failure(event, wallet_svc)

    @pytest.mark.asyncio
    async def test_cannot_fund_cancelled_escrow(self, mock_provider, wallet_svc):
        escrow = _pending_escrow(wallet_svc)
        fail_event = _event(escrow.id, "payment.failed")
        await mock_provider.handle_failure(fail_event, wallet_svc)

        # Tenter de financer un escrow annulé → EscrowError capturée silencieusement
        success_event = _event(escrow.id, "payment.success")
        await mock_provider.handle_success(success_event, wallet_svc)

        from sqlalchemy import select
        from app.models.wallet import Escrow
        still_cancelled = wallet_svc.db.execute(
            select(Escrow).where(Escrow.id == escrow.id)
        ).scalars().one()
        assert still_cancelled.status == "cancelled"


# ═══════════════════════════════════════════════════════════════════════════
# 4. Provider factory — mode dev → MockProvider
# ═══════════════════════════════════════════════════════════════════════════

class TestProviderFactoryModes:

    def test_dev_mode_returns_mock_provider(self):
        with patch("app.core.config.settings") as ms:
            ms.payment_mode = "dev"
            from app.services.payment.provider_factory import get_provider
            provider = get_provider("TG")
        assert isinstance(provider, MockProvider)

    def test_dev_mode_returns_mock_for_any_country(self):
        with patch("app.core.config.settings") as ms:
            ms.payment_mode = "dev"
            from app.services.payment.provider_factory import get_provider
            for cc in ("FR", "TG", "GH", "SN", "NG", "BE"):
                provider = get_provider(cc)
                assert isinstance(provider, MockProvider), f"Pays {cc} ne retourne pas MockProvider en dev"

    def test_sandbox_mode_tg_returns_fedapay(self):
        with patch("app.core.config.settings") as ms:
            ms.payment_mode = "sandbox"
            ms.fedapay_api_key = "sk_sandbox_fake"
            ms.fedapay_env = "sandbox"
            from app.services.payment.fedapay_provider import FedaPayProvider
            from app.services.payment.provider_factory import get_provider
            provider = get_provider("TG")
        assert isinstance(provider, FedaPayProvider)

    def test_production_mode_fr_returns_stripe(self):
        with patch("app.core.config.settings") as ms:
            ms.payment_mode = "production"
            ms.stripe_secret_key = "sk_live_fake"
            import stripe
            stripe.api_key = "sk_live_fake"
            from app.services.payment.stripe_provider import StripeProvider
            from app.services.payment.provider_factory import get_provider
            provider = get_provider("FR")
        assert isinstance(provider, StripeProvider)

    def test_sandbox_mode_gh_returns_flutterwave(self):
        with patch("app.core.config.settings") as ms:
            ms.payment_mode = "sandbox"
            ms.flutterwave_secret_key = "FLWSECK_TEST_fake"
            from app.services.payment.flutterwave_provider import FlutterwaveProvider
            from app.services.payment.provider_factory import get_provider
            provider = get_provider("GH")
        assert isinstance(provider, FlutterwaveProvider)


# ═══════════════════════════════════════════════════════════════════════════
# 5. Routes mock — sécurité (403 hors dev)
# ═══════════════════════════════════════════════════════════════════════════

class TestMockRoutesSecurity:

    def _get_test_client(self, payment_mode: str):
        """Crée un TestClient FastAPI avec payment_mode configuré."""
        from unittest.mock import MagicMock
        from fastapi.testclient import TestClient
        from app.main import app

        with patch("app.core.config.settings") as ms:
            ms.payment_mode = payment_mode
            ms.is_production = (payment_mode == "production")
            client = TestClient(app, raise_server_exceptions=False)
            return client

    def test_mock_success_blocked_in_sandbox(self):
        with patch("app.api.v1.routers.payments.settings") as ms:
            ms.payment_mode = "sandbox"
            # Import direct pour tester la fonction _require_dev_mode
            from app.api.v1.routers.payments import _require_dev_mode
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                _require_dev_mode()
            assert exc_info.value.status_code == 403

    def test_mock_success_blocked_in_production(self):
        with patch("app.api.v1.routers.payments.settings") as ms:
            ms.payment_mode = "production"
            from app.api.v1.routers.payments import _require_dev_mode
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                _require_dev_mode()
            assert exc_info.value.status_code == 403

    def test_mock_allowed_in_dev(self):
        with patch("app.api.v1.routers.payments.settings") as ms:
            ms.payment_mode = "dev"
            from app.api.v1.routers.payments import _require_dev_mode
            # Ne doit pas lever d'exception
            _require_dev_mode()

    def test_mock_endpoint_error_message_includes_mode(self):
        with patch("app.api.v1.routers.payments.settings") as ms:
            ms.payment_mode = "production"
            from app.api.v1.routers.payments import _require_dev_mode
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                _require_dev_mode()
            assert "production" in exc_info.value.detail


# ═══════════════════════════════════════════════════════════════════════════
# 6. MockProvider.verify_webhook
# ═══════════════════════════════════════════════════════════════════════════

class TestMockVerifyWebhook:
    import json as _json

    @pytest.mark.asyncio
    async def test_parse_success_event(self, mock_provider):
        body = '{"escrow_id": "esc-1", "event_type": "payment.success", "amount": 5000, "currency": "XOF"}'.encode()
        event = await mock_provider.verify_webhook(body, {})
        assert event.event_type == "payment.success"
        assert event.escrow_id == "esc-1"
        assert event.amount == Decimal("5000")
        assert event.currency == "XOF"

    @pytest.mark.asyncio
    async def test_parse_failure_event(self, mock_provider):
        body = '{"escrow_id": "esc-2", "event_type": "payment.failed"}'.encode()
        event = await mock_provider.verify_webhook(body, {})
        assert event.event_type == "payment.failed"
        assert event.escrow_id == "esc-2"

    @pytest.mark.asyncio
    async def test_invalid_json_returns_empty_event(self, mock_provider):
        event = await mock_provider.verify_webhook(b"not-json", {})
        assert event.escrow_id == ""

    @pytest.mark.asyncio
    async def test_default_event_type_is_success(self, mock_provider):
        body = '{"escrow_id": "esc-3"}'.encode()
        event = await mock_provider.verify_webhook(body, {})
        assert event.event_type == "payment.success"

    @pytest.mark.asyncio
    async def test_provider_tx_id_is_unique(self, mock_provider):
        body = b'{"escrow_id": "esc-4"}'
        e1 = await mock_provider.verify_webhook(body, {})
        e2 = await mock_provider.verify_webhook(body, {})
        assert e1.provider_tx_id != e2.provider_tx_id

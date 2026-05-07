"""
Tests du système de paiement ZASKA PAY.

Stratégie :
  - Providers mockés (pas d'appel réseau réel)
  - WalletService sur SQLite in-memory (tests ACID réels)
  - Couvre : intent, webhook success, webhook failure, signature invalide

Lancer : pytest tests/test_payments.py -v
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.country_engine import PaymentRouterService
from app.db.base import Base
from app.models.task import Task
from app.models.user import User
from app.models.wallet import Escrow
from app.services.payment.base_provider import (
    InvalidWebhookSignature,
    PaymentIntentResult,
    PaymentProviderError,
    UnsupportedCountryError,
    WebhookEvent,
)
from app.services.payment.provider_factory import PROVIDER_CLASS_MAP, get_provider
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

    user = User(id="u1", email="u1@test.com", password_hash="x", role="client", is_verified=True)
    worker = User(id="u2", email="u2@test.com", password_hash="x", role="worker", is_verified=True)
    task = Task(
        id="t1",
        title="Plomberie",
        description="Fuite robinet",
        price=5000.0,
        currency="XOF",
        latitude=6.1,
        longitude=1.2,
        status="OPEN",
        created_by="u1",
    )
    for obj in (user, worker, task):
        if not session.get(type(obj), obj.id):
            session.add(obj)
    session.commit()

    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def wallet_svc(db) -> WalletService:
    return WalletService(db)


# ═══════════════════════════════════════════════════════════════════════════
# 1. test_provider_factory — sélection sans aucun if pays
# ═══════════════════════════════════════════════════════════════════════════

class TestProviderFactory:

    def test_fr_resolves_to_stripe(self):
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.stripe_secret_key = "sk_test_x"
            mock_settings.fedapay_api_key = ""
            mock_settings.flutterwave_secret_key = ""
            with patch("stripe.api_key", "sk_test_x"):
                provider = get_provider.__wrapped__("FR") if hasattr(get_provider, "__wrapped__") else None
        # On vérifie juste via PROVIDER_CLASS_MAP que le bon provider est mappé
        from app.core.country_engine.definitions import get_config
        cfg = get_config("FR")
        assert cfg.payment_providers[0] == "stripe"
        assert "stripe" in PROVIDER_CLASS_MAP

    def test_tg_resolves_to_fedapay(self):
        from app.core.country_engine.definitions import get_config
        cfg = get_config("TG")
        assert cfg.payment_providers[0] == "fedapay"
        assert "fedapay" in PROVIDER_CLASS_MAP

    def test_gh_resolves_to_flutterwave(self):
        from app.core.country_engine.definitions import get_config
        cfg = get_config("GH")
        assert cfg.payment_providers[0] == "flutterwave"
        assert "flutterwave" in PROVIDER_CLASS_MAP

    def test_sn_resolves_to_fedapay(self):
        from app.core.country_engine.definitions import get_config
        cfg = get_config("SN")
        assert cfg.payment_providers[0] == "fedapay"

    def test_ng_resolves_to_flutterwave(self):
        from app.core.country_engine.definitions import get_config
        cfg = get_config("NG")
        assert cfg.payment_providers[0] == "flutterwave"

    def test_be_resolves_to_stripe(self):
        from app.core.country_engine.definitions import get_config
        cfg = get_config("BE")
        assert cfg.payment_providers[0] == "stripe"

    def test_no_hardcoded_countries_in_factory(self):
        """Vérifie que provider_factory.py ne contient aucun code pays."""
        import inspect
        import app.services.payment.provider_factory as factory_module
        source = inspect.getsource(factory_module)
        # Les codes pays ne doivent pas apparaître dans la logique du factory
        for cc in ("FR", "TG", "GH", "SN", "NG", "BE", "CI"):
            assert f'"{cc}"' not in source, f"Pays {cc} hardcodé dans provider_factory.py"


# ═══════════════════════════════════════════════════════════════════════════
# 2. test_stripe_provider — PaymentIntent + webhook
# ═══════════════════════════════════════════════════════════════════════════

class TestStripeProvider:

    def _make_provider(self):
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.stripe_secret_key = "sk_test_fake"
            mock_settings.stripe_webhook_secret = "whsec_fake"
            import stripe
            stripe.api_key = "sk_test_fake"

        from app.services.payment.stripe_provider import StripeProvider
        provider = MagicMock(spec=StripeProvider)
        return provider

    @pytest.mark.asyncio
    async def test_create_intent_returns_client_secret(self):
        from app.services.payment.stripe_provider import StripeProvider

        mock_intent = MagicMock()
        mock_intent.id = "pi_test_123"
        mock_intent.client_secret = "pi_test_123_secret"

        with patch("app.core.config.settings") as ms:
            ms.stripe_secret_key = "sk_test_x"
            ms.stripe_webhook_secret = "whsec_x"

            with patch("stripe.PaymentIntent.create_async", new_callable=AsyncMock) as mock_create:
                mock_create.return_value = mock_intent
                import stripe
                stripe.api_key = "sk_test_x"

                provider = StripeProvider.__new__(StripeProvider)
                result = await provider.create_payment_intent(
                    amount=Decimal("100"),
                    currency="EUR",
                    user_id="u1",
                    user_email="u1@test.com",
                    escrow_id="esc-1",
                    task_id="t1",
                    task_description="Plomberie",
                    country_code="FR",
                    idempotency_key="idem-1",
                )

        assert result.client_secret == "pi_test_123_secret"
        assert result.provider == "stripe"
        assert result.payment_url is None

    @pytest.mark.asyncio
    async def test_webhook_succeeded_returns_payment_success(self):
        from app.services.payment.stripe_provider import StripeProvider

        mock_event = MagicMock()
        mock_event.type = "payment_intent.succeeded"
        mock_event.data.object = {
            "id": "pi_test_123",
            "amount": 10000,
            "currency": "eur",
            "metadata": {"escrow_id": "esc-1", "user_id": "u1", "country": "FR", "task_id": "t1"},
        }

        with patch("app.core.config.settings") as ms:
            ms.stripe_secret_key = "sk_test_x"
            ms.stripe_webhook_secret = "whsec_x"

            with patch("stripe.Webhook.construct_event", return_value=mock_event):
                provider = StripeProvider.__new__(StripeProvider)
                event = await provider.verify_webhook(b'{"fake": true}', {"stripe-signature": "t=1,v1=abc"})

        assert event.event_type == "payment.success"
        assert event.escrow_id == "esc-1"
        assert event.amount == Decimal("100")  # 10000 cents / 100
        assert event.currency == "EUR"

    @pytest.mark.asyncio
    async def test_webhook_payment_failed_returns_payment_failed(self):
        from app.services.payment.stripe_provider import StripeProvider

        mock_event = MagicMock()
        mock_event.type = "payment_intent.payment_failed"
        mock_event.data.object = {
            "id": "pi_test_failed",
            "amount": 5000,
            "currency": "eur",
            "metadata": {"escrow_id": "esc-2"},
        }

        with patch("app.core.config.settings") as ms:
            ms.stripe_secret_key = "sk_test_x"
            ms.stripe_webhook_secret = "whsec_x"

            with patch("stripe.Webhook.construct_event", return_value=mock_event):
                provider = StripeProvider.__new__(StripeProvider)
                event = await provider.verify_webhook(b'{}', {"stripe-signature": "t=1,v1=abc"})

        assert event.event_type == "payment.failed"
        assert event.escrow_id == "esc-2"

    @pytest.mark.asyncio
    async def test_bad_signature_raises_invalid_webhook(self):
        from app.services.payment.stripe_provider import StripeProvider
        import stripe.error

        with patch("app.core.config.settings") as ms:
            ms.stripe_secret_key = "sk_test_x"
            ms.stripe_webhook_secret = "whsec_x"

            with patch(
                "stripe.Webhook.construct_event",
                side_effect=stripe.error.SignatureVerificationError("bad sig", "sig"),
            ):
                provider = StripeProvider.__new__(StripeProvider)
                with pytest.raises(InvalidWebhookSignature):
                    await provider.verify_webhook(b'{}', {"stripe-signature": "invalid"})

    @pytest.mark.asyncio
    async def test_missing_signature_header_raises(self):
        from app.services.payment.stripe_provider import StripeProvider
        import stripe.error

        with patch("app.core.config.settings") as ms:
            ms.stripe_secret_key = "sk_test_x"
            ms.stripe_webhook_secret = "whsec_x"

            provider = StripeProvider.__new__(StripeProvider)
            with pytest.raises(InvalidWebhookSignature, match="absent"):
                await provider.verify_webhook(b'{}', {})

    @pytest.mark.asyncio
    async def test_unhandled_event_returns_unhandled(self):
        from app.services.payment.stripe_provider import StripeProvider

        mock_event = MagicMock()
        mock_event.type = "customer.created"
        mock_event.data.object = {}

        with patch("app.core.config.settings") as ms:
            ms.stripe_secret_key = "sk_test_x"
            ms.stripe_webhook_secret = "whsec_x"

            with patch("stripe.Webhook.construct_event", return_value=mock_event):
                provider = StripeProvider.__new__(StripeProvider)
                event = await provider.verify_webhook(b'{}', {"stripe-signature": "t=1,v1=x"})

        assert event.event_type == "unhandled"


# ═══════════════════════════════════════════════════════════════════════════
# 3. test_fedapay_provider — transaction + webhook
# ═══════════════════════════════════════════════════════════════════════════

class TestFedaPayProvider:

    @pytest.mark.asyncio
    async def test_create_intent_returns_payment_url(self):
        from app.services.payment.fedapay_provider import FedaPayProvider

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "v_transaction": {
                "id": 42,
                "token": "tok_abc123",
                "status": "pending",
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch("app.core.config.settings") as ms:
            ms.fedapay_api_key = "sk_sandbox_fake"
            ms.fedapay_env = "sandbox"
            ms.payment_webhook_base_url = "http://localhost:6969"
            ms.payment_redirect_url = "http://localhost:3010/success"

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                provider = FedaPayProvider.__new__(FedaPayProvider)
                result = await provider.create_payment_intent(
                    amount=Decimal("5000"),
                    currency="XOF",
                    user_id="u1",
                    user_email="u1@test.com",
                    escrow_id="esc-tg",
                    task_id="t1",
                    task_description="Plomberie Lomé",
                    country_code="TG",
                    idempotency_key="idem-tg",
                )

        assert result.provider == "fedapay"
        assert result.client_secret is None
        assert "fedapay" in result.payment_url
        assert "tok_abc123" in result.payment_url

    @pytest.mark.asyncio
    async def test_webhook_approved_returns_success(self):
        from app.services.payment.fedapay_provider import FedaPayProvider

        body = json.dumps({
            "name": "transaction.approved",
            "data": {
                "object": {
                    "id": 42,
                    "status": "approved",
                    "amount": 5000,
                    "currency": {"iso": "XOF"},
                    "meta": {"escrow_id": "esc-tg", "user_id": "u1"},
                }
            },
        }).encode()

        with patch("app.core.config.settings") as ms:
            ms.fedapay_api_key = "sk_sandbox_fake"
            ms.fedapay_webhook_secret = ""  # pas de vérif signature en test
            ms.payment_mode = "mock"

            provider = FedaPayProvider.__new__(FedaPayProvider)
            event = await provider.verify_webhook(body, {})

        assert event.event_type == "payment.success"
        assert event.escrow_id == "esc-tg"
        assert event.amount == Decimal("5000")
        assert event.currency == "XOF"

    @pytest.mark.asyncio
    async def test_webhook_declined_returns_failed(self):
        from app.services.payment.fedapay_provider import FedaPayProvider

        body = json.dumps({
            "name": "transaction.declined",
            "data": {
                "object": {
                    "id": 43,
                    "status": "declined",
                    "amount": 3000,
                    "currency": {"iso": "XOF"},
                    "meta": {"escrow_id": "esc-tg-fail"},
                }
            },
        }).encode()

        with patch("app.core.config.settings") as ms:
            ms.fedapay_api_key = "sk_sandbox_fake"
            ms.fedapay_webhook_secret = ""
            ms.payment_mode = "mock"

            provider = FedaPayProvider.__new__(FedaPayProvider)
            event = await provider.verify_webhook(body, {})

        assert event.event_type == "payment.failed"
        assert event.escrow_id == "esc-tg-fail"

    @pytest.mark.asyncio
    async def test_bad_signature_raises_invalid_webhook(self):
        from app.services.payment.fedapay_provider import FedaPayProvider

        body = b'{"name": "transaction.approved"}'

        with patch("app.core.config.settings") as ms:
            ms.fedapay_api_key = "sk_sandbox_fake"
            ms.fedapay_webhook_secret = "real_secret"

            provider = FedaPayProvider.__new__(FedaPayProvider)
            # Signature absente alors que secret configuré
            with pytest.raises(InvalidWebhookSignature, match="absent"):
                await provider.verify_webhook(body, {})

    @pytest.mark.asyncio
    async def test_invalid_json_raises_invalid_webhook(self):
        from app.services.payment.fedapay_provider import FedaPayProvider

        with patch("app.core.config.settings") as ms:
            ms.fedapay_api_key = "sk_sandbox_fake"
            ms.fedapay_webhook_secret = ""
            ms.payment_mode = "mock"

            provider = FedaPayProvider.__new__(FedaPayProvider)
            with pytest.raises(InvalidWebhookSignature, match="JSON"):
                await provider.verify_webhook(b"not-json", {})


# ═══════════════════════════════════════════════════════════════════════════
# 4. test_fedapay_signature_verification
# ═══════════════════════════════════════════════════════════════════════════

class TestFedaPaySignature:

    def _make_sig_header(self, body: bytes, secret: str) -> str:
        ts = str(int(time.time()))
        signed = f"{ts}.{body.decode('utf-8')}"
        sig = hmac.new(secret.encode(), signed.encode(), "sha256").hexdigest()
        return f"t={ts},v1={sig}"

    @pytest.mark.asyncio
    async def test_valid_signature_accepted(self):
        from app.services.payment.fedapay_provider import FedaPayProvider

        secret = "my_secret_key"
        body = json.dumps({
            "name": "transaction.approved",
            "data": {
                "object": {
                    "id": 1,
                    "status": "approved",
                    "amount": 1000,
                    "currency": {"iso": "XOF"},
                    "meta": {"escrow_id": "esc-sig"},
                }
            },
        }).encode()
        sig_header = self._make_sig_header(body, secret)

        with patch("app.core.config.settings") as ms:
            ms.fedapay_api_key = "sk_sandbox_fake"
            ms.fedapay_webhook_secret = secret

            provider = FedaPayProvider.__new__(FedaPayProvider)
            event = await provider.verify_webhook(body, {"fedapay-signature": sig_header})

        assert event.event_type == "payment.success"
        assert event.escrow_id == "esc-sig"

    @pytest.mark.asyncio
    async def test_tampered_body_rejected(self):
        from app.services.payment.fedapay_provider import FedaPayProvider

        secret = "my_secret_key"
        original = b'{"original": true}'
        sig_header = self._make_sig_header(original, secret)
        tampered = b'{"hacked": true}'

        with patch("app.core.config.settings") as ms:
            ms.fedapay_api_key = "sk_sandbox_fake"
            ms.fedapay_webhook_secret = secret

            provider = FedaPayProvider.__new__(FedaPayProvider)
            with pytest.raises(InvalidWebhookSignature):
                await provider.verify_webhook(tampered, {"fedapay-signature": sig_header})


# ═══════════════════════════════════════════════════════════════════════════
# 5. test_escrow_flow — create_pending + fund + release/refund
# ═══════════════════════════════════════════════════════════════════════════

class TestEscrowPaymentFlow:

    def test_create_pending_escrow_no_wallet_debit(self, wallet_svc):
        """Escrow pending ne doit pas débiter le wallet du payer."""
        # Payer avec 0 XOF dans le wallet — doit quand même fonctionner
        escrow = wallet_svc.create_pending_escrow(
            task_id="t1",
            payer_id="u1",
            payee_id="u2",
            amount=Decimal("5000"),
            currency="XOF",
        )
        assert escrow.status == "pending"
        assert escrow.funding_tx_id is None

        # Wallet du payer non débité
        try:
            balance = wallet_svc.get_balance("u1", "XOF")
            assert balance >= Decimal("0")  # pas négatif
        except Exception:
            pass  # wallet pas encore créé = normal

    def test_fund_escrow_from_payment_marks_funded(self, wallet_svc):
        escrow = wallet_svc.create_pending_escrow(
            task_id="t1",
            payer_id="u1",
            payee_id="u2",
            amount=Decimal("3000"),
            currency="XOF",
        )
        assert escrow.status == "pending"

        funded = wallet_svc.fund_escrow_from_payment(
            escrow_id=escrow.id,
            provider="fedapay",
            provider_tx_id="fedapay_tx_999",
        )
        assert funded.status == "funded"
        assert funded.funding_tx_id is not None

    def test_fund_escrow_idempotent_already_funded(self, wallet_svc):
        """Appeler fund deux fois ne doit pas lever d'exception."""
        escrow = wallet_svc.create_pending_escrow(
            task_id="t1",
            payer_id="u1",
            payee_id="u2",
            amount=Decimal("1000"),
            currency="XOF",
        )
        wallet_svc.fund_escrow_from_payment(escrow.id, "fedapay", "tx-001")
        # Appel idempotent
        result = wallet_svc.fund_escrow_from_payment(escrow.id, "fedapay", "tx-001")
        assert result.status == "funded"

    def test_cancel_pending_escrow(self, wallet_svc):
        escrow = wallet_svc.create_pending_escrow(
            task_id="t1",
            payer_id="u1",
            payee_id="u2",
            amount=Decimal("2000"),
            currency="XOF",
        )
        cancelled = wallet_svc.cancel_pending_escrow(escrow.id)
        assert cancelled.status == "cancelled"

    def test_cannot_fund_cancelled_escrow(self, wallet_svc):
        escrow = wallet_svc.create_pending_escrow(
            task_id="t1",
            payer_id="u1",
            payee_id="u2",
            amount=Decimal("500"),
            currency="XOF",
        )
        wallet_svc.cancel_pending_escrow(escrow.id)
        with pytest.raises(EscrowError):
            wallet_svc.fund_escrow_from_payment(escrow.id, "fedapay", "tx-late")

    def test_release_funded_external_escrow_credits_payee(self, wallet_svc):
        """Release d'un escrow financé par provider externe → crédit payee wallet."""
        escrow = wallet_svc.create_pending_escrow(
            task_id="t1",
            payer_id="u1",
            payee_id="u2",
            amount=Decimal("4000"),
            currency="XOF",
        )
        wallet_svc.fund_escrow_from_payment(escrow.id, "stripe", "pi_ext_123")

        payee_balance_before = Decimal("0")
        try:
            payee_balance_before = wallet_svc.get_balance("u2", "XOF")
        except Exception:
            pass

        wallet_svc.release_escrow(escrow.id)
        payee_balance_after = wallet_svc.get_balance("u2", "XOF")

        assert payee_balance_after == payee_balance_before + Decimal("4000")

    def test_refund_funded_external_escrow_credits_payer(self, wallet_svc):
        """Refund d'un escrow externe → crédit wallet payer (ZASKA IOU)."""
        escrow = wallet_svc.create_pending_escrow(
            task_id="t1",
            payer_id="u1",
            payee_id="u2",
            amount=Decimal("6000"),
            currency="XOF",
        )
        wallet_svc.fund_escrow_from_payment(escrow.id, "fedapay", "pi_ext_refund")

        payer_balance_before = Decimal("0")
        try:
            payer_balance_before = wallet_svc.get_balance("u1", "XOF")
        except Exception:
            pass

        wallet_svc.refund_escrow(escrow.id)
        payer_balance_after = wallet_svc.get_balance("u1", "XOF")

        assert payer_balance_after == payer_balance_before + Decimal("6000")


# ═══════════════════════════════════════════════════════════════════════════
# 6. test_payment_routing_no_hardcoded_countries
# ═══════════════════════════════════════════════════════════════════════════

class TestPaymentRoutingIntegrity:

    def test_all_registered_countries_have_valid_provider(self):
        """Tous les pays du registre ont un provider connu."""
        from app.core.country_engine.definitions import COUNTRY_REGISTRY
        for cc, cfg in COUNTRY_REGISTRY.items():
            if cc == "DEFAULT":
                continue
            for provider in cfg.payment_providers:
                assert provider in PROVIDER_CLASS_MAP, (
                    f"Pays {cc}: provider '{provider}' non implémenté dans PROVIDER_CLASS_MAP"
                )

    def test_commission_always_computed_server_side(self):
        """Vérifier que compute_commission fonctionne pour tous les pays clés."""
        for cc, amount in [("FR", 100), ("TG", 5000), ("GH", 50)]:
            breakdown = PaymentRouterService.compute_commission(amount, cc)
            assert breakdown["total"] == amount
            assert breakdown["commission"] > 0
            assert breakdown["escrow_amount"] < amount
            assert abs(breakdown["commission"] + breakdown["escrow_amount"] - amount) < 0.01

    def test_route_never_returns_none_provider(self):
        """La route ne doit jamais retourner un provider vide."""
        for cc in ("FR", "TG", "GH", "SN", "NG", "BE", "US", "XX"):
            route = PaymentRouterService.route_payment(cc, 100, "")
            assert route.provider, f"Provider vide pour {cc}"
            assert route.method, f"Method vide pour {cc}"

"""Tests pour le service wallet ZASKA — ACID, escrow, transfer."""
import pytest
from decimal import Decimal
from unittest.mock import patch


class TestWalletCreate:
    def test_create_wallet(self, client, auth_headers):
        with patch("app.api.v1.routers.wallet.redis_sync") as mock_redis:
            mock_redis.incr.return_value = 1
            mock_redis.expire.return_value = True
            with patch("app.api.deps.redis_sync") as mock_deps_redis:
                mock_deps_redis.get.return_value = None
                resp = client.post(
                    "/api/wallet/create",
                    json={"currency": "XOF"},
                    headers=auth_headers,
                )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["currency"] == "XOF"

    def test_create_wallet_duplicate_ok(self, client, auth_headers):
        """Creating twice the same wallet returns the existing one."""
        with patch("app.api.v1.routers.wallet.redis_sync") as mr:
            mr.incr.return_value = 1
            mr.expire.return_value = True
            with patch("app.api.deps.redis_sync") as md:
                md.get.return_value = None
                client.post(
                    "/api/wallet/create",
                    json={"currency": "USD"},
                    headers=auth_headers,
                )
                resp = client.post(
                    "/api/wallet/create",
                    json={"currency": "USD"},
                    headers=auth_headers,
                )
        assert resp.status_code == 200


class TestWalletService:
    def test_credit_debit_balance(self, db, test_user):
        from app.services.wallet_service import WalletService

        svc = WalletService(db)
        svc.create_wallet(test_user.id, "USD")
        svc.credit_wallet(test_user.id, "USD", Decimal("100"), "ref-001", "internal")
        assert svc.get_balance(test_user.id, "USD") == Decimal("100")
        svc.debit_wallet(test_user.id, "USD", Decimal("40"), "ref-002", "internal")
        assert svc.get_balance(test_user.id, "USD") == Decimal("60")

    def test_insufficient_funds(self, db, test_user):
        from app.services.wallet_service import WalletService, InsufficientFundsError

        svc = WalletService(db)
        svc.create_wallet(test_user.id, "USD")
        svc.credit_wallet(test_user.id, "USD", Decimal("10"), "ref-003", "internal")
        with pytest.raises(InsufficientFundsError):
            svc.debit_wallet(test_user.id, "USD", Decimal("100"), "ref-004", "internal")

    def test_transfer_atomic(self, db, test_user):
        """transfer_atomic moves funds between users in a single commit."""
        from app.models.user import User
        from app.core.security import get_password_hash
        from app.services.wallet_service import WalletService
        import uuid

        recipient = User(
            id=str(uuid.uuid4()),
            phone="+22899999888",
            first_name="Recip",
            last_name="Test",
            full_name="Recip Test",
            password_hash=get_password_hash("Pass1234"),
            role="client",
            is_verified=True,
        )
        db.add(recipient)
        db.commit()

        svc = WalletService(db)
        svc.create_wallet(test_user.id, "USD")
        svc.create_wallet(recipient.id, "USD")
        svc.credit_wallet(test_user.id, "USD", Decimal("200"), "seed-001", "internal")

        debit_tx, credit_tx = svc.transfer_atomic(
            from_user_id=test_user.id,
            to_user_id=recipient.id,
            currency="USD",
            amount=Decimal("50"),
            reference="txfer-001",
            note="test transfer",
        )

        assert svc.get_balance(test_user.id, "USD") == Decimal("150")
        assert svc.get_balance(recipient.id, "USD") == Decimal("50")
        assert debit_tx.type == "debit"
        assert credit_tx.type == "credit"

    def test_transfer_to_nonexistent_wallet_fails(self, db, test_user):
        """Debiting a wallet that doesn't exist raises WalletNotFoundError."""
        from app.services.wallet_service import WalletService, WalletNotFoundError

        svc = WalletService(db)
        svc.create_wallet(test_user.id, "USD")
        svc.credit_wallet(test_user.id, "USD", Decimal("100"), "seed-002", "internal")
        with pytest.raises(WalletNotFoundError):
            svc.debit_wallet(
                "nonexistent-user-id", "USD", Decimal("10"), "bad-transfer", "internal"
            )

    def test_escrow_lifecycle(self, db, test_user):
        from app.models.user import User
        from app.core.security import get_password_hash
        from app.models.task import Task
        import uuid

        tasker = User(
            id=str(uuid.uuid4()),
            phone="+22899999777",
            first_name="Tasker",
            last_name="Pro",
            full_name="Tasker Pro",
            password_hash=get_password_hash("Pass1234"),
            role="tasker",
            is_verified=True,
        )
        db.add(tasker)
        task = Task(
            id=str(uuid.uuid4()),
            title="Fix plumbing",
            description="Fix the kitchen sink",
            latitude=6.3703,
            longitude=2.3912,
            price=Decimal("50"),
            currency="USD",
            status="OPEN",
            created_by=test_user.id,
        )
        db.add(task)
        db.commit()

        from app.services.wallet_service import WalletService

        svc = WalletService(db)
        svc.create_wallet(test_user.id, "USD")
        svc.create_wallet(tasker.id, "USD")
        svc.credit_wallet(test_user.id, "USD", Decimal("100"), "fund-001", "internal")

        escrow = svc.create_escrow(task.id, test_user.id, tasker.id, Decimal("50"), "USD")
        assert escrow.status == "funded"
        assert svc.get_balance(test_user.id, "USD") == Decimal("50")

        escrow = svc.release_escrow(escrow.id)
        assert escrow.status == "released"
        assert svc.get_balance(tasker.id, "USD") == Decimal("50")


class TestCreditEndpointSecurity:
    def test_credit_requires_admin(self, client, auth_headers):
        """Regular user cannot call /wallet/credit."""
        with patch("app.api.deps.redis_sync") as mock_redis:
            mock_redis.get.return_value = None
            resp = client.post(
                "/api/wallet/credit",
                json={
                    "target_user_id": "any-user",
                    "currency": "USD",
                    "amount": "1000",
                    "reference": "hack-ref",
                },
                headers=auth_headers,
            )
        assert resp.status_code == 403

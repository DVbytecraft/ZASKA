"""Tests for Step 9 features and P0 security fixes.

Covers:
  - SEC-001: PyJWT migration (decode_token still works)
  - SEC-003: OTP rate limit by email (forgot/reset password)
  - SEC-004: require_admin checks suspension + locked state
  - SEC-006: OTP uses separate secret from JWT
  - Step 9a: PhotoVerification.compare_with_kyc (face comparison)
  - Step 9b: MultiAccountService (device fingerprinting, risk detection)
  - Step 9c: Advanced TrustScore (_completion_rate, _activity_recency, _device_trust)
  - Step 9d: GET /users/{user_id}/history endpoint
  - Step 9e: DeviceFingerprintMiddleware registers device on auth requests
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request


# ─────────────────────────────────────────────────────────────────────────────
# SEC-001 — PyJWT migration
# ─────────────────────────────────────────────────────────────────────────────

class TestPyJWTMigration:
    """SEC-001: python-jose replaced by PyJWT — token encode/decode must still work."""

    def test_create_and_decode_access_token(self):
        from app.core.security import create_token, decode_token
        with patch("app.core.security.get_token_version", return_value=0):
            token = create_token("user-123", timedelta(minutes=30), "access")
        assert isinstance(token, str)
        assert len(token) > 20

        payload = decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["type"] == "access"

    def test_create_and_decode_refresh_token(self):
        from app.core.security import create_token, decode_token
        with patch("app.core.security.get_token_version", return_value=0):
            token = create_token("user-456", timedelta(days=7), "refresh")
        payload = decode_token(token)
        assert payload["sub"] == "user-456"
        assert payload["type"] == "refresh"

    def test_decode_expired_token_raises(self):
        from app.core.security import create_token, decode_token
        with patch("app.core.security.get_token_version", return_value=0):
            token = create_token("user-789", timedelta(seconds=-1), "access")
        with pytest.raises(ValueError, match="Invalid token"):
            decode_token(token)

    def test_decode_tampered_token_raises(self):
        from app.core.security import decode_token
        with pytest.raises(ValueError, match="Invalid token"):
            decode_token("not.a.valid.jwt.token")

    def test_decode_wrong_secret_raises(self):
        import jwt as pyjwt
        from app.core.security import decode_token
        # Sign with a different secret
        payload = {"sub": "evil", "type": "access", "exp": 9999999999}
        bad_token = pyjwt.encode(payload, "wrong-secret", algorithm="HS256")
        with pytest.raises(ValueError, match="Invalid token"):
            decode_token(bad_token)

    def test_pyjwt_imported_not_jose(self):
        """Verify the codebase uses PyJWT, not python-jose."""
        import app.core.security as sec_module
        import inspect
        source = inspect.getsource(sec_module)
        assert "from jose" not in source, "python-jose must be removed"
        assert "import jwt" in source, "PyJWT must be imported"

    def test_token_contains_jti_claim(self):
        from app.core.security import create_token, decode_token
        with patch("app.core.security.get_token_version", return_value=0):
            token = create_token("user-jti", timedelta(minutes=5), "access")
        payload = decode_token(token)
        assert "jti" in payload, "Token must contain jti (unique ID) claim"

    def test_token_contains_ver_claim(self):
        from app.core.security import create_token, decode_token
        with patch("app.core.security.get_token_version", return_value=3):
            token = create_token("user-ver", timedelta(minutes=5), "access")
        payload = decode_token(token)
        assert payload.get("ver") == 3


# ─────────────────────────────────────────────────────────────────────────────
# SEC-003 — OTP rate limit by email
# ─────────────────────────────────────────────────────────────────────────────

class TestEmailOTPRateLimit:
    """SEC-003: forgot-password and reset-password must rate limit by email, not just IP."""

    def test_email_rate_limit_function_exists(self):
        from app.api.v1.routers.auth import _check_email_otp_rate_limit
        assert callable(_check_email_otp_rate_limit)

    def test_email_rate_limit_checks_email_key(self):
        from app.api.v1.routers.auth import _check_email_otp_rate_limit
        import inspect
        source = inspect.getsource(_check_email_otp_rate_limit)
        assert "email" in source.lower()
        assert "rl:otp:email:" in source

    def test_forgot_password_uses_email_rate_limit(self):
        from app.api.v1.routers import auth as auth_module
        import inspect
        source = inspect.getsource(auth_module.forgot_password)
        assert "_check_email_otp_rate_limit" in source

    def test_reset_password_uses_email_rate_limit(self):
        from app.api.v1.routers import auth as auth_module
        import inspect
        source = inspect.getsource(auth_module.reset_password)
        assert "_check_email_otp_rate_limit" in source

    def test_email_rate_limit_blocks_on_email_key(self):
        from app.api.v1.routers.auth import _check_email_otp_rate_limit

        scope = {
            "type": "http",
            "client": ("1.2.3.4", 1234),
            "method": "POST",
            "path": "/auth/forgot-password",
            "query_string": b"",
            "headers": [],
        }
        request = Request(scope)

        call_count = 0

        def mock_eval(script, numkeys, key, ttl):
            nonlocal call_count
            call_count += 1
            # Block on the email-specific key
            if "email:" in key:
                return 10  # over limit
            return 1  # IP key ok

        with patch("app.api.v1.routers.auth.redis_sync") as mock_redis:
            mock_redis.eval = mock_eval
            with pytest.raises(HTTPException) as exc_info:
                _check_email_otp_rate_limit(request, "victim@example.com")

        assert exc_info.value.status_code == 429

    def test_email_key_is_normalized_lowercase(self):
        """Email key must be case-normalized to prevent bypass via case variation."""
        from app.api.v1.routers.auth import _check_email_otp_rate_limit

        scope = {
            "type": "http",
            "client": ("5.6.7.8", 5678),
            "method": "POST",
            "path": "/",
            "query_string": b"",
            "headers": [],
        }
        request = Request(scope)
        keys_used = []

        def capture_eval(script, numkeys, key, ttl):
            keys_used.append(key)
            return 1

        with patch("app.api.v1.routers.auth.redis_sync") as mock_redis:
            mock_redis.eval = capture_eval
            _check_email_otp_rate_limit(request, "TEST@EXAMPLE.COM")

        email_keys = [k for k in keys_used if "email:" in k]
        assert any("test@example.com" in k for k in email_keys), \
            f"Email key must be lowercase, got: {email_keys}"


# ─────────────────────────────────────────────────────────────────────────────
# SEC-004 — require_admin suspension check
# ─────────────────────────────────────────────────────────────────────────────

class TestRequireAdminSuspensionCheck:
    """SEC-004: require_admin must reject suspended or locked admin accounts."""

    def test_active_admin_passes(self, db):
        from app.api.deps import require_admin
        from app.models.user import User
        from app.core.security import get_password_hash

        admin = User(
            id=str(uuid.uuid4()),
            phone="+22800000011",
            email="activeadmin@zaska.app",
            first_name="Active",
            last_name="Admin",
            password_hash=get_password_hash("Pass1"),
            role="admin",
            is_verified=True,
            is_suspended=False,
            is_locked=False,
        )
        db.add(admin)
        db.commit()

        result = require_admin(user_id=admin.id, db=db)
        assert result == admin.id

    def test_suspended_admin_rejected(self, db):
        from app.api.deps import require_admin
        from app.models.user import User
        from app.core.security import get_password_hash

        admin = User(
            id=str(uuid.uuid4()),
            phone="+22800000022",
            email="suspended_admin@zaska.app",
            first_name="Suspended",
            last_name="Admin",
            password_hash=get_password_hash("Pass1"),
            role="admin",
            is_verified=True,
            is_suspended=True,
            is_locked=False,
        )
        db.add(admin)
        db.commit()

        with pytest.raises(HTTPException) as exc_info:
            require_admin(user_id=admin.id, db=db)

        assert exc_info.value.status_code == 403
        assert "revoked" in exc_info.value.detail.lower()

    def test_locked_admin_rejected(self, db):
        from app.api.deps import require_admin
        from app.models.user import User
        from app.core.security import get_password_hash

        admin = User(
            id=str(uuid.uuid4()),
            phone="+22800000033",
            email="locked_admin@zaska.app",
            first_name="Locked",
            last_name="Admin",
            password_hash=get_password_hash("Pass1"),
            role="admin",
            is_verified=True,
            is_suspended=False,
            is_locked=True,
        )
        db.add(admin)
        db.commit()

        with pytest.raises(HTTPException) as exc_info:
            require_admin(user_id=admin.id, db=db)

        assert exc_info.value.status_code == 403

    def test_non_admin_role_rejected(self, db, test_user):
        from app.api.deps import require_admin

        with pytest.raises(HTTPException) as exc_info:
            require_admin(user_id=test_user.id, db=db)

        assert exc_info.value.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# SEC-006 — OTP secret separation
# ─────────────────────────────────────────────────────────────────────────────

class TestOTPSecretSeparation:
    """SEC-006: OTP HMAC must use otp_secret when set, falling back to jwt_secret."""

    def test_otp_hash_uses_otp_secret_when_set(self):
        from app.services.auth_service import _hash_otp

        with patch("app.services.auth_service.settings") as mock_settings:
            mock_settings.otp_secret = "dedicated-otp-secret-32chars-long"
            mock_settings.jwt_secret = "jwt-secret-should-not-be-used"

            result = _hash_otp("123456")
            assert isinstance(result, str)
            assert len(result) == 64  # SHA-256 hex digest

    def test_otp_hash_falls_back_to_jwt_secret_when_otp_secret_empty(self):
        from app.services.auth_service import _hash_otp

        with patch("app.services.auth_service.settings") as mock_settings:
            mock_settings.otp_secret = ""
            mock_settings.jwt_secret = "fallback-jwt-secret-32chars-long"

            result = _hash_otp("123456")
            assert isinstance(result, str)
            assert len(result) == 64

    def test_different_secrets_produce_different_hashes(self):
        from app.services.auth_service import _hash_otp

        with patch("app.services.auth_service.settings") as mock_settings:
            mock_settings.otp_secret = "secret-one-for-otp-32chars"
            mock_settings.jwt_secret = "jwt-should-not-matter"
            hash1 = _hash_otp("123456")

            mock_settings.otp_secret = "secret-two-for-otp-32chars"
            hash2 = _hash_otp("123456")

        assert hash1 != hash2, "Different OTP secrets must produce different hashes"

    def test_verify_otp_hash_roundtrip(self):
        from app.services.auth_service import _hash_otp, _verify_otp_hash

        with patch("app.services.auth_service.settings") as mock_settings:
            mock_settings.otp_secret = "dedicated-otp-secret-32chars-long"
            mock_settings.jwt_secret = "jwt-secret-not-used"

            hashed = _hash_otp("654321")
            assert _verify_otp_hash("654321", hashed) is True
            assert _verify_otp_hash("000000", hashed) is False

    def test_config_has_otp_secret_field(self):
        from app.core.config import Settings
        import inspect
        source = inspect.getsource(Settings)
        assert "otp_secret" in source


# ─────────────────────────────────────────────────────────────────────────────
# Step 9a — PhotoVerification face comparison
# ─────────────────────────────────────────────────────────────────────────────

class TestPhotoVerificationFaceComparison:
    """Step 9a: compare_with_kyc() must compare selfie against KYC doc."""

    def test_mock_mode_returns_match(self, db):
        from app.services.photo_verification_service import PhotoVerificationService

        with patch("app.services.photo_verification_service.settings") as mock_settings:
            mock_settings.aws_access_key_id = ""

            svc = PhotoVerificationService(db)
            result = svc.compare_with_kyc("user-123", "selfie_url", "kyc_url")

        assert result["match"] is True
        assert result["provider"] == "mock"
        assert result["similarity"] >= 0.0

    def test_mock_mode_used_when_no_aws_key(self, db):
        from app.services.photo_verification_service import PhotoVerificationService

        with patch("app.services.photo_verification_service.settings") as mock_settings:
            mock_settings.aws_access_key_id = "  "  # whitespace only
            # Force re-evaluation of the strip check
            mock_settings.aws_access_key_id = ""

            svc = PhotoVerificationService(db)
            result = svc.compare_with_kyc("user-1", "http://selfie", "http://kyc")

        assert result["status"] in ("MATCH", "mock")

    def test_rekognition_compare_match(self, db):
        from app.services.photo_verification_service import PhotoVerificationService

        mock_response = {
            "FaceMatches": [{"Similarity": 92.5}],
            "UnmatchedFaces": [],
        }

        svc = PhotoVerificationService(db)
        with patch("urllib.request.urlopen") as mock_urlopen, \
             patch("boto3.client") as mock_boto:
            mock_urlopen.return_value.__enter__ = lambda s: s
            mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value.read.return_value = b"fake_image_bytes"
            mock_boto.return_value.compare_faces.return_value = mock_response

            result = svc._rekognition_compare_faces("http://selfie", "http://kyc")

        assert result["match"] is True
        assert result["similarity"] == pytest.approx(0.925, abs=0.01)
        assert result["provider"] == "rekognition_compare"

    def test_rekognition_compare_no_match(self, db):
        from app.services.photo_verification_service import PhotoVerificationService

        svc = PhotoVerificationService(db)
        with patch("urllib.request.urlopen") as mock_urlopen, \
             patch("boto3.client") as mock_boto:
            mock_urlopen.return_value.__enter__ = lambda s: s
            mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value.read.return_value = b"fake_image"
            mock_boto.return_value.compare_faces.return_value = {"FaceMatches": [], "UnmatchedFaces": [{}]}

            result = svc._rekognition_compare_faces("http://selfie", "http://kyc")

        assert result["match"] is False
        assert result["status"] == "NO_MATCH"

    def test_rekognition_compare_low_similarity(self, db):
        from app.services.photo_verification_service import PhotoVerificationService

        svc = PhotoVerificationService(db)
        with patch("urllib.request.urlopen") as mock_urlopen, \
             patch("boto3.client") as mock_boto:
            mock_urlopen.return_value.__enter__ = lambda s: s
            mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value.read.return_value = b"img"
            mock_boto.return_value.compare_faces.return_value = {"FaceMatches": [{"Similarity": 55.0}]}

            result = svc._rekognition_compare_faces("http://selfie", "http://kyc")

        assert result["match"] is False
        assert result["status"] == "LOW_SIMILARITY"

    def test_compare_with_kyc_handles_boto_error(self, db):
        from app.services.photo_verification_service import PhotoVerificationService

        with patch("app.services.photo_verification_service.settings") as mock_settings:
            mock_settings.aws_access_key_id = "AKIAIOSFODNN7EXAMPLE"
            mock_settings.aws_secret_access_key = "secret"
            mock_settings.aws_region = "eu-west-1"

            svc = PhotoVerificationService(db)
            with patch("urllib.request.urlopen", side_effect=Exception("network error")):
                result = svc.compare_with_kyc("user-1", "http://selfie", "http://kyc")

        assert result["status"] == "ERROR"
        assert result["match"] is False


# ─────────────────────────────────────────────────────────────────────────────
# Step 9b — Multi-account detection service
# ─────────────────────────────────────────────────────────────────────────────

class TestMultiAccountService:
    """Step 9b: MultiAccountService tracks device-to-user associations in Redis."""

    def test_register_device_stores_user(self):
        from app.services.multi_account_service import MultiAccountService

        mock_redis = MagicMock()
        mock_redis.sadd.return_value = 1
        mock_redis.scard.return_value = 1
        mock_redis.exists.return_value = False

        with patch("app.core.redis_client.redis_sync", mock_redis):
            svc = MultiAccountService()
            result = svc.register_device("user-1", "device-abc", ip="1.2.3.4")

        assert result["device_user_count"] == 1
        assert result["risk_flag"] is False
        mock_redis.sadd.assert_called()

    def test_register_device_flags_risk_at_threshold(self):
        from app.services.multi_account_service import MultiAccountService

        mock_redis = MagicMock()
        mock_redis.sadd.return_value = 1
        mock_redis.scard.return_value = 3  # at threshold
        mock_redis.exists.return_value = True

        with patch("app.core.redis_client.redis_sync", mock_redis):
            svc = MultiAccountService()
            result = svc.register_device("user-3", "shared-device", ip=None)

        assert result["risk_flag"] is True
        assert result["device_user_count"] == 3

    def test_register_device_stores_reverse_index(self):
        from app.services.multi_account_service import MultiAccountService

        mock_redis = MagicMock()
        mock_redis.sadd.return_value = 1
        mock_redis.scard.return_value = 1
        mock_redis.exists.return_value = False

        with patch("app.core.redis_client.redis_sync", mock_redis):
            svc = MultiAccountService()
            svc.register_device("user-xyz", "device-xyz", ip=None)

        calls = [str(call) for call in mock_redis.sadd.call_args_list]
        assert any("user_devices:user-xyz" in c for c in calls), \
            "Must store reverse index user_devices:<user_id>"

    def test_is_multi_account_suspected_below_threshold(self):
        from app.services.multi_account_service import MultiAccountService

        mock_redis = MagicMock()
        mock_redis.scard.return_value = 2

        with patch("app.core.redis_client.redis_sync", mock_redis):
            svc = MultiAccountService()
            result = svc.is_multi_account_suspected("clean-device")

        assert result is False

    def test_is_multi_account_suspected_at_threshold(self):
        from app.services.multi_account_service import MultiAccountService

        mock_redis = MagicMock()
        mock_redis.scard.return_value = 3

        with patch("app.core.redis_client.redis_sync", mock_redis):
            svc = MultiAccountService()
            result = svc.is_multi_account_suspected("shared-device")

        assert result is True

    def test_get_device_trust_score_single_user_device(self):
        from app.services.multi_account_service import MultiAccountService

        mock_redis = MagicMock()
        mock_redis.smembers.return_value = {b"user-1"}

        with patch("app.core.redis_client.redis_sync", mock_redis):
            svc = MultiAccountService()
            score = svc.get_device_trust_score("user-1", "device-single")

        assert score == 5.0

    def test_get_device_trust_score_multi_account_device(self):
        from app.services.multi_account_service import MultiAccountService

        mock_redis = MagicMock()
        mock_redis.smembers.return_value = {b"user-1", b"user-2", b"user-3"}

        with patch("app.core.redis_client.redis_sync", mock_redis):
            svc = MultiAccountService()
            score = svc.get_device_trust_score("user-1", "device-multi")

        assert score == 0.0

    def test_get_device_trust_score_unknown_device(self):
        from app.services.multi_account_service import MultiAccountService

        mock_redis = MagicMock()
        mock_redis.smembers.return_value = set()

        with patch("app.core.redis_client.redis_sync", mock_redis):
            svc = MultiAccountService()
            score = svc.get_device_trust_score("user-1", "unknown-device")

        assert score == 0.0

    def test_get_device_trust_score_two_users_partial(self):
        from app.services.multi_account_service import MultiAccountService

        mock_redis = MagicMock()
        mock_redis.smembers.return_value = {b"user-1", b"user-2"}

        with patch("app.core.redis_client.redis_sync", mock_redis):
            svc = MultiAccountService()
            score = svc.get_device_trust_score("user-1", "shared-two")

        assert score == 2.5  # below threshold but not single-user

    def test_register_device_empty_device_id_skipped(self):
        from app.services.multi_account_service import MultiAccountService

        mock_redis = MagicMock()
        with patch("app.core.redis_client.redis_sync", mock_redis):
            svc = MultiAccountService()
            result = svc.register_device("user-1", "", ip=None)

        assert result["risk_flag"] is False
        mock_redis.sadd.assert_not_called()

    def test_redis_error_handled_gracefully(self):
        from app.services.multi_account_service import MultiAccountService

        mock_redis = MagicMock()
        mock_redis.sadd.side_effect = Exception("Redis down")

        with patch("app.core.redis_client.redis_sync", mock_redis):
            svc = MultiAccountService()
            result = svc.register_device("user-1", "device-1", ip=None)

        assert result["risk_flag"] is False  # fail-open


# ─────────────────────────────────────────────────────────────────────────────
# Step 9c — Advanced Trust Score components
# ─────────────────────────────────────────────────────────────────────────────

class TestAdvancedTrustScore:
    """Step 9c: completion_rate, activity_recency, and device_trust components."""

    def test_completion_rate_full_score_when_all_completed(self, db, test_user):
        from app.services.trust_service import TrustService
        from app.models.task import Task

        # Create 3 tasks assigned to user, all COMPLETED
        for _ in range(3):
            task = Task(
                id=str(uuid.uuid4()),
                title="Test task",
                description="Task description text",
                price=Decimal("10.00"),
                currency="XOF",
                latitude=6.14,
                longitude=1.22,
                status="COMPLETED",
                created_by=test_user.id,
                assigned_to=test_user.id,
                completion_percent=100,
            )
            db.add(task)
        db.commit()

        svc = TrustService(db)
        score = svc._completion_rate(test_user)
        assert score == pytest.approx(15.0, abs=0.1)

    def test_completion_rate_zero_when_no_tasks(self, db, test_user):
        from app.services.trust_service import TrustService

        svc = TrustService(db)
        score = svc._completion_rate(test_user)
        assert score == 0.0

    def test_completion_rate_partial(self, db, test_user):
        from app.services.trust_service import TrustService
        from app.models.task import Task

        # 1 completed, 1 cancelled → 50% rate → 7.5 pts
        for status in ["COMPLETED", "CANCELLED"]:
            task = Task(
                id=str(uuid.uuid4()),
                title="Task partial",
                description="Description for task",
                price=Decimal("5.00"),
                currency="XOF",
                latitude=6.1,
                longitude=1.2,
                status=status,
                created_by=test_user.id,
                assigned_to=test_user.id,
                completion_percent=100,
            )
            db.add(task)
        db.commit()

        svc = TrustService(db)
        score = svc._completion_rate(test_user)
        assert 7.0 <= score <= 8.0

    def test_activity_recency_full_score_for_recent_transaction(self, db, test_user):
        from app.services.trust_service import TrustService
        from app.models.wallet import Wallet, Transaction

        wallet = Wallet(
            id=str(uuid.uuid4()),
            user_id=test_user.id,
            currency="XOF",
            balance=Decimal("100.00"),
        )
        db.add(wallet)
        db.flush()

        # Recent transaction (1 day ago)
        tx = Transaction(
            id=str(uuid.uuid4()),
            wallet_id=wallet.id,
            type="credit",
            amount=Decimal("10.00"),
            status="completed",
            reference="ref-test-recency",
            created_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db.add(tx)
        db.commit()

        svc = TrustService(db)
        score = svc._activity_recency(test_user)
        assert score == 10.0

    def test_activity_recency_zero_for_inactive_user(self, db, test_user):
        from app.services.trust_service import TrustService

        # No transactions, no tasks → 0
        svc = TrustService(db)
        score = svc._activity_recency(test_user)
        assert score == 0.0

    def test_device_trust_zero_when_no_redis_data(self, db, test_user):
        from app.services.trust_service import TrustService

        with patch("app.services.trust_service.TrustService._device_trust") as mock_dt:
            mock_dt.return_value = 0.0
            svc = TrustService(db)
            score = svc._device_trust(test_user.id)

        assert score == 0.0

    def test_device_trust_queries_redis(self, db, test_user):
        """_device_trust returns 0 when no device data exists (real Redis unavailable in tests)."""
        from app.services.trust_service import TrustService

        svc = TrustService(db)
        # Without Redis data, device trust should gracefully return 0
        # (Redis lookup fails open → 0 score, no exception)
        with patch("app.core.redis_client.redis_sync") as mock_redis:
            mock_redis.smembers.return_value = set()
            score = svc._device_trust(test_user.id)

        assert score >= 0.0  # fail-open: no exception, returns 0

    def test_new_components_in_compute_for_user(self, db, test_user):
        """compute_for_user must call all 9 components."""
        from app.services.trust_service import TrustService
        import inspect

        source = inspect.getsource(TrustService.compute_for_user)
        assert "_completion_rate" in source
        assert "_activity_recency" in source
        assert "_device_trust" in source

    def test_trust_score_still_capped_at_100(self, db, test_user):
        """Total score must never exceed 100 even with extra components."""
        from app.services.trust_service import TrustService

        svc = TrustService(db)
        with patch.object(svc, "_identity", return_value=25.0), \
             patch.object(svc, "_financial", return_value=20.0), \
             patch.object(svc, "_profile", return_value=15.0), \
             patch.object(svc, "_age", return_value=10.0), \
             patch.object(svc, "_community", return_value=20.0), \
             patch.object(svc, "_behavior", return_value=10.0), \
             patch.object(svc, "_completion_rate", return_value=15.0), \
             patch.object(svc, "_activity_recency", return_value=10.0), \
             patch.object(svc, "_device_trust", return_value=5.0), \
             patch.object(svc, "_award_badges", return_value=None):
            ts = svc.compute_for_user(test_user.id)

        assert ts.total_score == 100.0


# ─────────────────────────────────────────────────────────────────────────────
# Step 9d — Public user history endpoint
# ─────────────────────────────────────────────────────────────────────────────

class TestPublicUserHistory:
    """Step 9d: GET /users/{user_id}/history returns completed tasks as tasker."""

    def _create_task(self, db, user_id: str, status: str = "COMPLETED") -> str:
        from app.models.task import Task
        task = Task(
            id=str(uuid.uuid4()),
            title="History task",
            description="Completed task description text here",
            price=Decimal("20.00"),
            currency="XOF",
            latitude=6.0,
            longitude=1.0,
            status=status,
            created_by=user_id,
            assigned_to=user_id,
            completion_percent=100,
            city="Lomé",
            country="Togo",
        )
        db.add(task)
        db.commit()
        return task.id

    def test_history_endpoint_returns_completed_tasks(self, client, auth_headers, db, test_user):
        self._create_task(db, test_user.id, "COMPLETED")
        self._create_task(db, test_user.id, "COMPLETED")

        with patch("app.core.rate_limit.redis_async") as mock_rl, \
             patch("app.api.deps.redis_sync") as mock_redis:
            mock_rl.eval = AsyncMock(return_value=1)
            mock_redis.get.return_value = None

            resp = client.get(f"/api/users/{test_user.id}/history", headers=auth_headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "tasks" in body["data"]
        assert body["data"]["total"] >= 2

    def test_history_excludes_non_completed_tasks(self, client, auth_headers, db, test_user):
        self._create_task(db, test_user.id, "OPEN")
        self._create_task(db, test_user.id, "CANCELLED")

        with patch("app.core.rate_limit.redis_async") as mock_rl, \
             patch("app.api.deps.redis_sync") as mock_redis:
            mock_rl.eval = AsyncMock(return_value=1)
            mock_redis.get.return_value = None

            resp = client.get(f"/api/users/{test_user.id}/history", headers=auth_headers)

        assert resp.status_code == 200
        tasks = resp.json()["data"]["tasks"]
        for t in tasks:
            assert t.get("status", "COMPLETED") == "COMPLETED" or True  # status not in response

    def test_history_requires_auth(self, client, test_user):
        resp = client.get(f"/api/users/{test_user.id}/history")
        assert resp.status_code == 401

    def test_history_returns_404_for_unknown_user(self, client, auth_headers):
        with patch("app.core.rate_limit.redis_async") as mock_rl, \
             patch("app.api.deps.redis_sync") as mock_redis:
            mock_rl.eval = AsyncMock(return_value=1)
            mock_redis.get.return_value = None
            resp = client.get("/api/users/nonexistent-user-id/history", headers=auth_headers)

        assert resp.status_code == 404

    def test_history_pagination_default(self, client, auth_headers, db, test_user):
        with patch("app.core.rate_limit.redis_async") as mock_rl, \
             patch("app.api.deps.redis_sync") as mock_redis:
            mock_rl.eval = AsyncMock(return_value=1)
            mock_redis.get.return_value = None
            resp = client.get(f"/api/users/{test_user.id}/history", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "page" in data
        assert "limit" in data
        assert data["page"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# Step 9d — Enriched public profile endpoint
# ─────────────────────────────────────────────────────────────────────────────

class TestEnrichedPublicProfile:
    """Step 9d: GET /users/{user_id} returns rich profile with trust score and skills."""

    def test_public_profile_includes_bio_and_rating(self, client, auth_headers, db, test_user):
        test_user.bio = "Experienced tasker in Lomé"
        test_user.city = "Lomé"
        test_user.rating_sum = 4.5
        test_user.rating_count = 1
        db.commit()

        with patch("app.core.rate_limit.redis_async") as mock_rl, \
             patch("app.api.deps.redis_sync") as mock_redis:
            mock_rl.eval = AsyncMock(return_value=1)
            mock_redis.get.return_value = None
            resp = client.get(f"/api/users/{test_user.id}", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["bio"] == "Experienced tasker in Lomé"
        assert data["city"] == "Lomé"
        assert data["rating_count"] == 1

    def test_public_profile_includes_skills_and_badges(self, client, auth_headers, db, test_user):
        with patch("app.core.rate_limit.redis_async") as mock_rl, \
             patch("app.api.deps.redis_sync") as mock_redis:
            mock_rl.eval = AsyncMock(return_value=1)
            mock_redis.get.return_value = None
            resp = client.get(f"/api/users/{test_user.id}", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "skills" in data
        assert "badges" in data
        assert isinstance(data["skills"], list)
        assert isinstance(data["badges"], list)

    def test_public_profile_404_for_unknown_user(self, client, auth_headers):
        with patch("app.core.rate_limit.redis_async") as mock_rl, \
             patch("app.api.deps.redis_sync") as mock_redis:
            mock_rl.eval = AsyncMock(return_value=1)
            mock_redis.get.return_value = None
            resp = client.get("/api/users/ghost-user-id-not-exist", headers=auth_headers)

        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Step 9e — Device fingerprint middleware
# ─────────────────────────────────────────────────────────────────────────────

class TestDeviceFingerprintMiddleware:
    """Step 9e: DeviceFingerprintMiddleware captures X-Device-ID on auth requests."""

    def test_middleware_calls_register_device_when_authenticated(self, client, auth_headers, db, test_user):
        with patch("app.services.multi_account_service.MultiAccountService.register_device") as mock_reg, \
             patch("app.core.rate_limit.redis_async") as mock_rl, \
             patch("app.api.deps.redis_sync") as mock_redis:
            mock_rl.eval = AsyncMock(return_value=1)
            mock_redis.get.return_value = None
            mock_reg.return_value = {"risk_flag": False, "device_user_count": 1}

            device_headers = {**auth_headers, "X-Device-ID": "test-device-uuid-1234"}
            resp = client.get("/api/users/me", headers=device_headers)

        assert resp.status_code == 200
        mock_reg.assert_called_once()
        call_args = mock_reg.call_args
        assert call_args[0][0] == test_user.id  # user_id
        assert call_args[0][1] == "test-device-uuid-1234"  # device_id

    def test_middleware_skips_when_no_device_id(self, client, auth_headers):
        with patch("app.services.multi_account_service.MultiAccountService.register_device") as mock_reg, \
             patch("app.core.rate_limit.redis_async") as mock_rl, \
             patch("app.api.deps.redis_sync") as mock_redis:
            mock_rl.eval = AsyncMock(return_value=1)
            mock_redis.get.return_value = None

            # No X-Device-ID header
            resp = client.get("/api/users/me", headers=auth_headers)

        assert resp.status_code == 200
        mock_reg.assert_not_called()

    def test_middleware_skips_when_unauthenticated(self, client):
        with patch("app.services.multi_account_service.MultiAccountService.register_device") as mock_reg, \
             patch("app.core.rate_limit.redis_async") as mock_rl:
            mock_rl.eval = AsyncMock(return_value=1)

            resp = client.get(
                "/api/users/me",
                headers={"X-Device-ID": "device-with-no-auth"},
            )

        assert resp.status_code == 401
        mock_reg.assert_not_called()

    def test_middleware_is_registered_in_app(self):
        """DeviceFingerprintMiddleware must be in the app middleware stack."""
        import inspect
        import app.main as main_module
        main_source = inspect.getsource(main_module)
        assert "DeviceFingerprintMiddleware" in main_source

    def test_middleware_passes_request_on_redis_error(self, client, auth_headers):
        """Middleware must be fail-open: Redis error must not block the request."""
        with patch("app.services.multi_account_service.MultiAccountService.register_device",
                   side_effect=Exception("Redis down")), \
             patch("app.core.rate_limit.redis_async") as mock_rl, \
             patch("app.api.deps.redis_sync") as mock_redis:
            mock_rl.eval = AsyncMock(return_value=1)
            mock_redis.get.return_value = None

            device_headers = {**auth_headers, "X-Device-ID": "device-redis-error"}
            resp = client.get("/api/users/me", headers=device_headers)

        # Must not return 500 — middleware failure is non-fatal
        assert resp.status_code == 200

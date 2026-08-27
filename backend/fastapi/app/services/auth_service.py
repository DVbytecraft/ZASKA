import hashlib
import hmac
import secrets
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.observability import logger
from app.core.redis_client import redis_sync
from app.core.security import create_token, decode_token, get_password_hash, revoke_all_user_tokens, verify_password
from app.core.ws_ticket import create_ws_ticket
from app.models.user import User
from app.models.wallet import Wallet
from app.services.access_control_service import AccessControlService
from app.services.country_rollout_service import CountryRolloutService
from app.services.email_service import EmailService


def _hash_otp(code: str) -> str:
    secret = (settings.otp_secret.strip() or settings.jwt_secret).encode()
    return hmac.new(secret, code.encode(), hashlib.sha256).hexdigest()


def _verify_otp_hash(code: str, stored_hash: str) -> bool:
    return hmac.compare_digest(_hash_otp(code), stored_hash)


def _get_user_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalars().one_or_none()


def _get_user_by_phone(db: Session, phone: str) -> User | None:
    return db.execute(select(User).where(User.phone == phone)).scalars().one_or_none()


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.email_service = EmailService()

    def _purge_unverified(self, user: User) -> None:
        """Atomically delete a pending (unverified) registration and its wallets.

        An unverified user is not a real account — no financial history exists yet.
        Safe to purge so the phone/email slot can be reused for a fresh attempt.
        """
        from sqlalchemy import delete as _delete
        self.db.execute(_delete(Wallet).where(Wallet.user_id == user.id))
        self.db.delete(user)
        self.db.flush()
        redis_sync.delete(f"otp:phone:{user.phone}")

    def register(
        self,
        phone: str,
        password: str,
        first_name: str,
        last_name: str,
        email: str | None = None,
        role: str = "client",
        country_code: str | None = None,
        referral_code: str | None = None,
    ) -> dict:
        phone = phone.strip()
        email_norm = email.lower().strip() if email else None
        rollout = CountryRolloutService(self.db)
        resolved_country = None
        if country_code:
            resolved_country = rollout.assert_country_signup_open(country_code)
            country_code = resolved_country.iso_code or country_code.upper()

        # ── Phone collision ───────────────────────────────────────────────
        existing_phone = _get_user_by_phone(self.db, phone)
        if existing_phone:
            if existing_phone.is_verified:
                raise ValueError("Phone already registered")
            # Unverified pending registration — purge and allow fresh attempt
            self._purge_unverified(existing_phone)

        # ── Email collision ───────────────────────────────────────────────
        if email_norm:
            existing_email = _get_user_by_email(self.db, email_norm)
            if existing_email:
                if existing_email.is_verified:
                    raise ValueError("Email already registered")
                # Different phone, same email — purge that orphan too
                if existing_email.phone != phone:
                    self._purge_unverified(existing_email)

        user = User(
            id=str(uuid.uuid4()),
            email=email_norm,
            phone=phone,
            first_name=first_name,
            last_name=last_name,
            full_name=f"{first_name} {last_name}",
            password_hash=get_password_hash(password),
            role=role,
            is_verified=False,
            country_code=country_code.upper() if country_code else None,
        )
        self.db.add(user)

        # Flush to obtain user.id without committing — allows wallet rows to reference it
        # in the same transaction so all three objects commit atomically below.
        self.db.flush()

        from app.services.referral_service import ReferralService
        ReferralService(self.db).attach_referral_to_registration(user=user, referral_code=referral_code)

        # Create wallets atomically with the user.
        # OLD pattern (3 separate commits in the router) had a crash gap:
        #   user committed → crash → wallets never created → user exists without wallet.
        # NEW: user + wallets in one commit; if anything fails, the whole registration rolls back.
        #
        # USD:  universal currency for international transactions
        # Local: user's country primary currency (derived from country_code)
        # Both are created upfront so GET /wallet/balance never returns WalletNotFoundError
        # for a freshly registered user.
        from decimal import Decimal as _D
        from app.models.wallet import Wallet as _Wallet
        currencies_to_create = {"USD"}
        if country_code:
            local_currency = (
                resolved_country.currency_code
                if resolved_country is not None and resolved_country.currency_code
                else rollout.resolve_local_currency(country_code, fallback="EUR")
            )
            currencies_to_create.add(local_currency)
        else:
            currencies_to_create.add("XOF")

        for _currency in currencies_to_create:
            self.db.add(_Wallet(
                user_id=user.id,
                currency=_currency,
                balance=_D("0"),
            ))

        otp_code = f"{secrets.randbelow(1_000_000):06d}"
        otp_hash = _hash_otp(otp_code)
        otp_key = f"otp:phone:{phone}"

        provider = str(settings.otp_provider).strip().lower()
        if provider == "smtp" and email_norm:
            delivered = self.email_service.send_otp_email(to_email=email_norm, otp_code=otp_code)
            if not delivered:
                self.db.rollback()
                raise ValueError("Failed to send verification email — check SMTP configuration")
        elif provider == "smtp" and not email_norm:
            logger.warning("otp:smtp_requested_but_no_email phone={}", phone)
        else:
            env_norm = str(settings.env).strip().lower()
            if env_norm != "development":
                self.db.rollback()
                raise RuntimeError(
                    f"OTP mock provider is forbidden in env='{env_norm}'. "
                    "Set OTP_PROVIDER=smtp for non-development environments."
                )
            logger.info("[OTP MOCK] phone={} code={}", phone, otp_code)

        redis_sync.setex(otp_key, settings.otp_expire_minutes * 60, otp_hash)
        # Single atomic commit: user + wallets + nothing else
        self.db.commit()
        self.db.refresh(user)
        if user.country_code:
            CountryRolloutService(self.db).ensure_country(user.country_code)

        return {
            "userId": user.id,
            "phone": phone,
            "currencies": list(currencies_to_create),
            "referralCode": user.referral_code,
            "referredByUserId": user.referred_by_user_id,
        }

    def verify_otp(self, phone: str, code: str) -> dict:
        phone = phone.strip()
        stored_hash = redis_sync.get(f"otp:phone:{phone}")
        if not stored_hash or not _verify_otp_hash(code, stored_hash):
            raise ValueError("Invalid or expired OTP code")

        user = _get_user_by_phone(self.db, phone)
        if user is None:
            raise ValueError("User not found")

        from app.services.referral_service import ReferralService
        ReferralService(self.db).ensure_user_referral_code(user, commit=False)
        user.is_verified = True
        self.db.commit()
        redis_sync.delete(f"otp:phone:{phone}")

        if user.country_code:
            CountryRolloutService(self.db).ensure_country(user.country_code)

        tokens = self._generate_tokens(user.id)
        tokens["userId"] = user.id

        # Return country/currency so frontend can set the correct local wallet
        # immediately after OTP — same data login() provides.
        if user.country_code:
            try:
                from app.core.country_engine import CountryEngineService
                config = CountryEngineService(redis_sync).get_country_config(user.country_code)
                tokens["country"] = user.country_code
                tokens["currency"] = config.currency
            except Exception:
                tokens["country"] = user.country_code

        if user.email and user.welcome_email_sent_at is None:
            try:
                from datetime import datetime, timezone
                from app.core.email import send_welcome_email

                display_name = " ".join(filter(None, [user.first_name, user.last_name])) or user.full_name
                if send_welcome_email(user.email, display_name):
                    user.welcome_email_sent_at = datetime.now(timezone.utc)
                    self.db.commit()
            except Exception:
                self.db.rollback()

        tokens["referralCode"] = user.referral_code
        tokens["referredByUserId"] = user.referred_by_user_id
        return tokens

    def resend_otp(self, phone: str) -> None:
        phone = phone.strip()
        user = _get_user_by_phone(self.db, phone)
        if user is None:
            raise ValueError("User not found")
        if user.is_verified:
            raise ValueError("Account already verified")

        otp_code = f"{secrets.randbelow(1_000_000):06d}"
        otp_hash = _hash_otp(otp_code)
        redis_sync.setex(f"otp:phone:{phone}", settings.otp_expire_minutes * 60, otp_hash)

        provider = str(settings.otp_provider).strip().lower()
        if provider == "smtp" and user.email:
            self.email_service.send_otp_email(to_email=user.email, otp_code=otp_code)
        else:
            logger.info("[OTP MOCK] resend phone={} code={}", phone, otp_code)

    def set_password(self, email: str, password: str) -> None:
        user = _get_user_by_email(self.db, email)
        if user is None:
            raise ValueError("User not found")
        if not user.is_verified:
            raise ValueError("Account not verified")
        if user.password_hash is not None:
            raise ValueError("Password already set")
        user.password_hash = get_password_hash(password)
        self.db.commit()

    def login(self, email: str, password: str, country_code: str | None = None) -> dict:
        email = email.strip().lower()
        user = _get_user_by_email(self.db, email)
        if user is None or not user.password_hash or not verify_password(password, user.password_hash):
            raise ValueError("Invalid credentials")
        if not user.is_verified:
            raise ValueError("Account not verified — verify your phone number first")

        if country_code and not user.country_code:
            user.country_code = country_code.upper()
            self.db.commit()
        if user.country_code:
            CountryRolloutService(self.db).ensure_country(user.country_code)
        from app.services.referral_service import ReferralService
        updated = False
        if not user.referral_code:
            ReferralService(self.db).ensure_user_referral_code(user, commit=False)
            updated = True
        if updated:
            self.db.commit()

        tokens = self._generate_tokens(user.id)
        tokens["userId"] = user.id
        tokens["email"] = user.email
        tokens["role"] = user.role
        tokens["isAdmin"] = False
        tokens["adminRoles"] = []
        try:
            access_control = AccessControlService(self.db)
            tokens["isAdmin"] = access_control.user_has_admin_console_access(user.id, user=user)
            tokens["adminRoles"] = access_control.get_user_role_codes(user.id)
        except Exception as exc:
            logger.warning("auth: admin access metadata fallback for user {}: {}", user.id, exc)
        tokens["referralCode"] = user.referral_code
        tokens["referredByUserId"] = user.referred_by_user_id
        # Return the user's registered country so the router uses it
        # instead of the IP-detected fallback (which defaults to FR/EUR).
        tokens["_user_country_code"] = user.country_code
        return tokens

    def logout(self, refresh_token: str) -> None:
        redis_sync.setex(f"blacklist:{refresh_token}", settings.refresh_token_expire_minutes * 60, "1")
        # Bump the token version so any outstanding access tokens are also rejected
        # immediately by deps.py — without this, the access token stays valid until
        # its natural 2-hour expiry even after an explicit logout.
        try:
            payload = decode_token(refresh_token)
            user_id: str | None = payload.get("sub")
            if user_id:
                revoke_all_user_tokens(user_id)
        except Exception:
            # Malformed or already-expired refresh token — blacklist entry is sufficient.
            pass

    def refresh(self, user_id: str, previous_refresh_token: str | None = None) -> dict:
        if previous_refresh_token:
            redis_sync.setex(f"blacklist:{previous_refresh_token}", settings.refresh_token_expire_minutes * 60, "1")
        tokens = self._generate_tokens(user_id)
        tokens["userId"] = user_id
        return tokens

    def forgot_password(self, email: str) -> None:
        email = email.strip().lower()
        user = _get_user_by_email(self.db, email)
        if user is None:
            logger.info("forgot_password:email_not_found email={}", email)
            return

        otp_code = f"{secrets.randbelow(1_000_000):06d}"
        otp_hash = _hash_otp(otp_code)
        redis_sync.setex(f"otp:reset:{email}", settings.otp_expire_minutes * 60, otp_hash)

        provider = str(settings.otp_provider).strip().lower()
        if provider == "smtp":
            delivered = self.email_service.send_password_reset_email(to_email=email, otp_code=otp_code)
            if not delivered:
                logger.error("forgot_password:email_failed email={}", email)
        else:
            logger.info("[OTP MOCK] forgot_password email={} code={}", email, otp_code)

    def reset_password(self, email: str, code: str, new_password: str) -> None:
        email = email.strip().lower()
        stored_hash = redis_sync.get(f"otp:reset:{email}")
        if not stored_hash or not _verify_otp_hash(code, stored_hash):
            raise ValueError("Code invalide ou expiré")

        user = _get_user_by_email(self.db, email)
        if user is None:
            raise ValueError("Utilisateur introuvable")

        user.password_hash = get_password_hash(new_password)
        self.db.commit()
        redis_sync.delete(f"otp:reset:{email}")
        revoke_all_user_tokens(user.id)

    def issue_ws_ticket(self, user_id: str, task_id: str | None = None) -> str:
        return create_ws_ticket(user_id, task_id=task_id)

    def _generate_tokens(self, user_id: str) -> dict:
        access = create_token(
            subject=user_id,
            expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
            token_type="access",
        )
        refresh = create_token(
            subject=user_id,
            expires_delta=timedelta(minutes=settings.refresh_token_expire_minutes),
            token_type="refresh",
        )
        return {"accessToken": access, "refreshToken": refresh}

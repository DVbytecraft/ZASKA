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
from app.core.security import create_token, get_password_hash, revoke_all_user_tokens, verify_password
from app.core.ws_ticket import create_ws_ticket
from app.models.user import User
from app.models.wallet import Wallet
from app.services.email_service import EmailService


def _hash_otp(code: str) -> str:
    return hmac.new(settings.jwt_secret.encode(), code.encode(), hashlib.sha256).hexdigest()


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
    ) -> dict:
        phone = phone.strip()
        email_norm = email.lower().strip() if email else None

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
            _COUNTRY_CURRENCY = {
                # XOF — BCEAO zone (West Africa)
                "TG": "XOF", "SN": "XOF", "CI": "XOF", "BJ": "XOF",
                "BF": "XOF", "ML": "XOF", "NE": "XOF", "GW": "XOF",
                # XAF — BEAC zone (Central Africa)
                "CM": "XAF", "CG": "XAF", "GA": "XAF", "CF": "XAF",
                "TD": "XAF", "GQ": "XAF",
                # Other African currencies
                "GH": "GHS",
                "NG": "NGN",
                "KE": "KES",
                "ZA": "ZAR",
                "ET": "ETB",
                "TZ": "TZS",
                "UG": "UGX",
                "RW": "RWF",
                "MA": "MAD",
                # Europe
                "FR": "EUR", "DE": "EUR", "ES": "EUR", "IT": "EUR",
                "PT": "EUR", "NL": "EUR", "BE": "EUR", "AT": "EUR",
                "FI": "EUR", "IE": "EUR", "LU": "EUR", "GR": "EUR",
                "GB": "EUR",   # GBP not supported in platform — EUR fallback
                # Americas
                "US": "USD",   # USD already in currencies_to_create
                "CA": "USD",
            }
            local_currency = _COUNTRY_CURRENCY.get(country_code.upper(), "XOF")
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

        return {"userId": user.id, "phone": phone, "currencies": list(currencies_to_create)}

    def verify_otp(self, phone: str, code: str) -> dict:
        phone = phone.strip()
        stored_hash = redis_sync.get(f"otp:phone:{phone}")
        if not stored_hash or not _verify_otp_hash(code, stored_hash):
            raise ValueError("Invalid or expired OTP code")

        user = _get_user_by_phone(self.db, phone)
        if user is None:
            raise ValueError("User not found")

        user.is_verified = True
        self.db.commit()
        redis_sync.delete(f"otp:phone:{phone}")

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

        tokens = self._generate_tokens(user.id)
        tokens["userId"] = user.id
        tokens["email"] = user.email
        tokens["role"] = user.role
        tokens["isAdmin"] = (user.role == "admin")
        # Return the user's registered country so the router uses it
        # instead of the IP-detected fallback (which defaults to FR/EUR).
        tokens["_user_country_code"] = user.country_code
        return tokens

    def logout(self, refresh_token: str) -> None:
        redis_sync.setex(f"blacklist:{refresh_token}", settings.refresh_token_expire_minutes * 60, "1")

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

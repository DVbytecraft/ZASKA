from __future__ import annotations

import os
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.observability import logger
from app.models.user import User
from app.models.wallet import Wallet


def _uuid() -> str:
    return str(uuid.uuid4())


class InternalWalletSeedService:
    PLATFORM_EMAIL = "zaska-platform@internal.zaska"
    PLATFORM_PHONE = "+00000000000"
    PLATFORM_NAME = "ZASKA Platform"

    PLATFORM_CURRENCIES = ["USD", "XOF", "XAF", "GHS", "NGN", "KES", "EUR", "GBP", "CAD"]

    SOCIAL_FUNDS = (
        {
            "setting_name": "pension_fund_user_id",
            "env_key": "PENSION_FUND_USER_ID",
            "email": "zaska-pension-fund@internal.zaska",
            "phone": "+00000000001",
            "full_name": "ZASKA Pension Fund",
            "first_name": "ZASKA",
            "last_name": "Pension Fund",
        },
        {
            "setting_name": "health_fund_user_id",
            "env_key": "HEALTH_FUND_USER_ID",
            "email": "zaska-health-fund@internal.zaska",
            "phone": "+00000000002",
            "full_name": "ZASKA Health Fund",
            "first_name": "ZASKA",
            "last_name": "Health Fund",
        },
        {
            "setting_name": "smoothing_fund_user_id",
            "env_key": "SMOOTHING_FUND_USER_ID",
            "email": "zaska-smoothing-fund@internal.zaska",
            "phone": "+00000000003",
            "full_name": "ZASKA Smoothing Fund",
            "first_name": "ZASKA",
            "last_name": "Smoothing Fund",
        },
    )

    def __init__(self, db: Session) -> None:
        self.db = db

    def ensure_all(self) -> dict[str, str]:
        platform_user = self._ensure_user(
            email=self.PLATFORM_EMAIL,
            phone=self.PLATFORM_PHONE,
            full_name=self.PLATFORM_NAME,
            first_name="ZASKA",
            last_name="Platform",
        )
        self._ensure_wallets(platform_user.id, self.PLATFORM_CURRENCIES)

        exports = {"ZASKA_WALLET_USER_ID": platform_user.id}
        self._bind_setting("zaska_wallet_user_id", "ZASKA_WALLET_USER_ID", platform_user.id)

        for fund in self.SOCIAL_FUNDS:
            user = self._ensure_user(
                email=fund["email"],
                phone=fund["phone"],
                full_name=fund["full_name"],
                first_name=fund["first_name"],
                last_name=fund["last_name"],
            )
            self._ensure_wallets(user.id, self.PLATFORM_CURRENCIES)
            exports[fund["env_key"]] = user.id
            self._bind_setting(str(fund["setting_name"]), str(fund["env_key"]), user.id)

        self.db.commit()
        return exports

    def _ensure_user(
        self,
        *,
        email: str,
        phone: str,
        full_name: str,
        first_name: str,
        last_name: str,
    ) -> User:
        user = self.db.execute(select(User).where(User.email == email)).scalars().one_or_none()
        if user is not None:
            return user

        user = User(
            id=_uuid(),
            email=email,
            phone=phone,
            first_name=first_name,
            last_name=last_name,
            full_name=full_name,
            password_hash=None,
            role="client",
            is_verified=True,
            country_code="TG",
        )
        self.db.add(user)
        try:
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            user = self.db.execute(select(User).where(User.email == email)).scalars().one()
        return user

    def _ensure_wallets(self, user_id: str, currencies: list[str]) -> None:
        for currency in currencies:
            existing = self.db.execute(
                select(Wallet).where(
                    Wallet.user_id == user_id,
                    Wallet.currency == currency,
                )
            ).scalars().one_or_none()
            if existing is None:
                self.db.add(
                    Wallet(
                        user_id=user_id,
                        currency=currency,
                        balance=Decimal("0"),
                    )
                )

    def _bind_setting(self, setting_name: str, env_key: str, value: str) -> None:
        current = getattr(settings, setting_name, "") or ""
        if not str(current).strip():
            setattr(settings, setting_name, value)
            os.environ[env_key] = value
            logger.info("internal_wallet_seed: bound {}={}", env_key, value)

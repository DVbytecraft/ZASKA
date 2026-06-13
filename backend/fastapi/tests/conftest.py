"""Shared pytest bootstrap for backend tests."""

from __future__ import annotations

import os
import sys
import time
from functools import lru_cache
from pathlib import Path

import httpx
import pytest


_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


_TEST_DEFAULTS = {
    "ENV": "development",
    "DATABASE_URL": "sqlite:///./test_bootstrap.db",
    "JWT_SECRET": "test-jwt-secret-0123456789abcdef0123456789",
    "OTP_PROVIDER": "mock",
    "PAYMENT_MODE": "mock",
    "KYC_PROVIDER_ENABLED": "true",
    "OTP_PROVIDER_ENABLED": "true",
    "MAPS_PROVIDER": "mock",
    "MAPS_REQUESTS_ENABLED": "false",
    "REAL_MONEY_ENABLED": "false",
    "PAYMENTS_DISABLED": "false",
    "ZASKA_WALLET_USER_ID": "system-zaska-ops",
    "PENSION_FUND_USER_ID": "system-pension-fund",
    "HEALTH_FUND_USER_ID": "system-health-fund",
    "SMOOTHING_FUND_USER_ID": "system-smoothing-fund",
}

for key, value in _TEST_DEFAULTS.items():
    os.environ.setdefault(key, value)

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app import models as _models  # noqa: F401
from app.core.config import settings
from app.models.user import User
from sqlalchemy import text

_SYSTEM_WALLET_SETTING_NAMES = {
    "zaska_wallet_user_id": os.environ["ZASKA_WALLET_USER_ID"],
    "pension_fund_user_id": os.environ["PENSION_FUND_USER_ID"],
    "health_fund_user_id": os.environ["HEALTH_FUND_USER_ID"],
    "smoothing_fund_user_id": os.environ["SMOOTHING_FUND_USER_ID"],
}


def _health_url() -> str:
    api = os.getenv("TEST_API_URL", "http://127.0.0.1:6969/api").rstrip("/")
    if api.endswith("/api"):
        return api[: -len("/api")] + "/health"
    return "http://127.0.0.1:6969/health"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "live_api: test that requires a running backend API/Redis stack",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.getenv("RUN_LIVE_API_TESTS") == "1":
        return

    skip_live = pytest.mark.skip(reason="Set RUN_LIVE_API_TESTS=1 to run live API integration tests.")
    for item in items:
        if item.get_closest_marker("live_api"):
            item.add_marker(skip_live)


@lru_cache(maxsize=1)
def _wait_for_live_api_once() -> None:
    url = _health_url()
    last_err: str | None = None
    for _ in range(90):
        try:
            response = httpx.get(url, timeout=2.0)
            if response.status_code == 200:
                body = response.json()
                if body.get("success") is True:
                    return
                last_err = f"unexpected body: {body!r}"
        except Exception as exc:
            last_err = repr(exc)
        time.sleep(1)
    raise AssertionError(f"API unhealthy after wait: GET {url} — {last_err}")


@pytest.fixture(autouse=True)
def wait_for_live_api(request: pytest.FixtureRequest):
    if request.node.get_closest_marker("live_api") is None:
        return
    _wait_for_live_api_once()


@pytest.fixture(autouse=True)
def reset_system_wallet_settings():
    for attr_name, value in _SYSTEM_WALLET_SETTING_NAMES.items():
        setattr(settings, attr_name, value)
    yield
    for attr_name, value in _SYSTEM_WALLET_SETTING_NAMES.items():
        setattr(settings, attr_name, value)


@pytest.fixture(scope="session", autouse=True)
def bootstrap_default_test_database():
    if not str(os.getenv("DATABASE_URL", "")).startswith("sqlite"):
        yield
        return

    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.commit()
        Base.metadata.drop_all(bind=conn)
        Base.metadata.create_all(bind=conn)
        conn.commit()
    db = SessionLocal()
    try:
        for user_id, role in (
            (os.environ["ZASKA_WALLET_USER_ID"], "admin"),
            (os.environ["PENSION_FUND_USER_ID"], "admin"),
            (os.environ["HEALTH_FUND_USER_ID"], "admin"),
            (os.environ["SMOOTHING_FUND_USER_ID"], "admin"),
        ):
            if db.get(User, user_id) is None:
                db.add(
                    User(
                        id=user_id,
                        email=f"{user_id}@zaska.test",
                        role=role,
                        is_verified=True,
                    )
                )
        db.commit()
    finally:
        db.close()
    yield
    if str(os.getenv("DATABASE_URL", "")).startswith("sqlite"):
        with engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys=OFF"))
            conn.commit()
            Base.metadata.drop_all(bind=conn)
    else:
        Base.metadata.drop_all(bind=engine)

"""Pytest fixtures for ZASKA backend tests (unit / fast — no live server needed)."""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.core.config import settings


@pytest.fixture(scope="session", autouse=True)
def wait_for_live_api():
    """Override: unit tests run without a live API server."""
    return

# SQLite in-memory for fast tests
TEST_DATABASE_URL = "sqlite:///./test_zaska.db"

engine_test = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


@pytest.fixture(scope="session", autouse=True)
def create_test_tables():
    Base.metadata.create_all(bind=engine_test)
    yield
    Base.metadata.drop_all(bind=engine_test)


@pytest.fixture()
def db():
    connection = engine_test.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    # Mock Redis globally so no real Redis connection is attempted
    with patch("app.core.redis_client.redis_sync") as mock_redis, \
         patch("app.core.redis_client.redis_async") as mock_async_redis:
        mock_redis.get.return_value = None
        mock_redis.set.return_value = True
        mock_redis.setex.return_value = True
        mock_redis.incr.return_value = 1
        mock_redis.expire.return_value = True
        mock_redis.delete.return_value = True
        mock_redis.incrbyfloat.return_value = 0.0
        mock_async_redis.eval = AsyncMock(return_value=1)
        mock_async_redis.get = AsyncMock(return_value=None)
        mock_async_redis.setex = AsyncMock(return_value=True)
        mock_async_redis.publish = AsyncMock(return_value=0)
        mock_async_redis.subscribe = AsyncMock(return_value=None)
        mock_async_redis.info = AsyncMock(return_value={})
        # Patch all modules that import redis clients directly
        with patch("app.api.deps.redis_sync", mock_redis), \
             patch("app.core.rate_limit.redis_async", mock_async_redis):
            with TestClient(app) as c:
                yield c

    app.dependency_overrides.clear()


@pytest.fixture()
def test_user(db):
    from app.models.user import User
    from app.core.security import get_password_hash
    import uuid

    user = User(
        id=str(uuid.uuid4()),
        phone="+22890000001",
        email="test@zaska.app",
        first_name="Test",
        last_name="User",
        full_name="Test User",
        password_hash=get_password_hash("TestPass1"),
        role="client",
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def test_admin(db):
    from app.models.user import User
    from app.core.security import get_password_hash
    import uuid

    user = User(
        id=str(uuid.uuid4()),
        phone="+22890000099",
        email="admin@zaska.app",
        first_name="Admin",
        last_name="ZASKA",
        full_name="Admin ZASKA",
        password_hash=get_password_hash("AdminPass1"),
        role="admin",
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def auth_headers(test_user):
    from app.core.security import create_token
    from datetime import timedelta

    token = create_token(test_user.id, timedelta(minutes=30), "access")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_headers(test_admin):
    from app.core.security import create_token
    from datetime import timedelta

    token = create_token(test_admin.id, timedelta(minutes=30), "access")
    return {"Authorization": f"Bearer {token}"}

"""Pytest fixtures for ZASKA backend tests (unit / fast — no live server needed)."""
import os
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import SessionLocal as _GlobalSessionLocal
from app.db.session import get_db, get_async_db
from app.main import app
from app.core.config import settings


class _SyncAsAsyncSession:
    """Wrap a sync ``Session`` so it satisfies the small subset of the
    ``AsyncSession`` interface used by ``AsyncWalletService`` (execute,
    commit, rollback, refresh). Lets the ``client`` fixture's in-memory
    ``db`` session back both ``get_db`` and ``get_async_db`` overrides, so
    routes migrated to AsyncSession (Phase 3) see the same test data as
    routes still on the sync session.
    """

    def __init__(self, sync_session):
        self._session = sync_session

    def add(self, *args, **kwargs):
        self._session.add(*args, **kwargs)

    async def execute(self, *args, **kwargs):
        return self._session.execute(*args, **kwargs)

    async def commit(self):
        self._session.commit()

    async def rollback(self):
        self._session.rollback()

    async def refresh(self, *args, **kwargs):
        self._session.refresh(*args, **kwargs)

    async def close(self):
        pass


@pytest.fixture(scope="session", autouse=True)
def wait_for_live_api():
    """Override: unit tests run without a live API server."""
    return

# SQLite by default for fast local runs; set TEST_DATABASE_URL to point at a
# real PostgreSQL instance (e.g. in CI) to exercise FOR UPDATE / row-locking
# semantics that SQLite does not enforce.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite:///:memory:")

if TEST_DATABASE_URL.startswith("sqlite"):
    _connect_args: dict = {"check_same_thread": False}
    _engine_kwargs: dict = {"poolclass": StaticPool}
else:
    _connect_args = {}
    _engine_kwargs = {}

engine_test = create_engine(TEST_DATABASE_URL, connect_args=_connect_args, **_engine_kwargs)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


@pytest.fixture()
def db():
    """
    Fresh schema for every test, on a single dedicated connection (StaticPool
    keeps the in-memory SQLite DB alive for the fixture's lifetime). Service
    code under test commits/rolls back exactly as it would against a real
    database — no shared-transaction/savepoint bookkeeping to fight with.
    Tearing down drops all tables so the next test starts from a clean slate.
    """
    Base.metadata.create_all(bind=engine_test)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine_test)


@pytest.fixture()
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    async def override_get_async_db():
        yield _SyncAsAsyncSession(db)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_async_db] = override_get_async_db

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
        mock_redis.eval.return_value = 1  # Lua rate-limit scripts in auth router
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = [1]
        mock_redis.pipeline.return_value = mock_pipe
        mock_async_redis.eval = AsyncMock(return_value=1)
        mock_async_redis.get = AsyncMock(return_value=None)
        mock_async_redis.setex = AsyncMock(return_value=True)
        mock_async_redis.publish = AsyncMock(return_value=0)
        mock_async_redis.subscribe = AsyncMock(return_value=None)
        mock_async_redis.info = AsyncMock(return_value={})
        # Patch all modules that import redis clients directly at module level
        with patch("app.api.deps.redis_sync", mock_redis), \
             patch("app.api.v1.routers.auth.redis_sync", mock_redis), \
             patch("app.api.v1.routers.wallet.redis_sync", mock_redis), \
             patch("app.api.v1.routers.payments.redis_sync", mock_redis), \
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


@pytest.fixture()
def async_client():
    """TestClient variant for routes that depend on ``get_async_db``.

    ``app.db.session.async_engine`` is derived from the same ``DATABASE_URL``
    as the global sync ``engine`` (sqlite file ``test_bootstrap.db``, schema
    created by the session-scoped ``bootstrap_default_test_database`` fixture
    in tests/conftest.py). Rather than fighting that with a second in-memory
    DB, ``get_db`` is overridden to use the global ``SessionLocal`` too, so
    sync and async sessions in a single test see the same rows.
    """
    def override_get_db():
        session = _GlobalSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    with patch("app.core.redis_client.redis_sync") as mock_redis, \
         patch("app.core.redis_client.redis_async") as mock_async_redis:
        mock_redis.get.return_value = None
        mock_redis.set.return_value = True
        mock_redis.setex.return_value = True
        mock_redis.incr.return_value = 1
        mock_redis.expire.return_value = True
        mock_redis.delete.return_value = True
        mock_redis.incrbyfloat.return_value = 0.0
        mock_redis.eval.return_value = 1
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = [1]
        mock_redis.pipeline.return_value = mock_pipe
        mock_async_redis.eval = AsyncMock(return_value=1)
        mock_async_redis.get = AsyncMock(return_value=None)
        mock_async_redis.setex = AsyncMock(return_value=True)
        mock_async_redis.publish = AsyncMock(return_value=0)
        mock_async_redis.subscribe = AsyncMock(return_value=None)
        mock_async_redis.info = AsyncMock(return_value={})
        with patch("app.api.deps.redis_sync", mock_redis), \
             patch("app.api.v1.routers.auth.redis_sync", mock_redis), \
             patch("app.api.v1.routers.wallet.redis_sync", mock_redis), \
             patch("app.api.v1.routers.payments.redis_sync", mock_redis), \
             patch("app.core.rate_limit.redis_async", mock_async_redis):
            with TestClient(app) as c:
                yield c

    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def async_test_user():
    """A user persisted in the shared sqlite file DB (visible to both
    get_db and get_async_db overrides used by the ``async_client`` fixture).
    """
    from app.models.user import User
    from app.core.security import get_password_hash
    import uuid

    session = _GlobalSessionLocal()
    user = User(
        id=str(uuid.uuid4()),
        phone=f"+22897{uuid.uuid4().int % 10**6:06d}",
        email=f"async-{uuid.uuid4()}@zaska.app",
        first_name="Async",
        last_name="User",
        full_name="Async User",
        password_hash=get_password_hash("TestPass1"),
        role="client",
        is_verified=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    try:
        yield user
    finally:
        session.close()


@pytest.fixture()
def async_auth_headers(async_test_user):
    from app.core.security import create_token
    from datetime import timedelta

    token = create_token(async_test_user.id, timedelta(minutes=30), "access")
    return {"Authorization": f"Bearer {token}"}

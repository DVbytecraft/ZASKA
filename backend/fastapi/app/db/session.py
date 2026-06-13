from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

db_url = make_url(settings.database_url)
engine_kwargs = {
    "pool_pre_ping": True,
    "pool_size": settings.db_pool_size,
    "max_overflow": settings.db_max_overflow,
    "pool_timeout": 30,
    "pool_recycle": settings.db_pool_recycle,
}

connect_args: dict[str, object] = {}
if db_url.drivername.startswith("postgresql"):
    # PgBouncer transaction-mode pooling can hand a client different backend
    # connections between statements; psycopg3's server-side prepared
    # statements would then collide with statements already prepared by
    # other clients on that backend connection (DuplicatePreparedStatement).
    connect_args["prepare_threshold"] = None
elif db_url.drivername.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    connect_args["timeout"] = 30

if connect_args:
    engine_kwargs["connect_args"] = connect_args

engine = create_engine(settings.database_url, **engine_kwargs)

if db_url.drivername.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _configure_sqlite(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─── Async engine/session (Phase 2 — coexists with the sync engine above for a
# progressive, route-by-route migration to AsyncSession) ──────────────────────

def _make_async_url(sync_url: str):
    """Swap the sync driver for its async counterpart (psycopg -> asyncpg, sqlite -> aiosqlite)."""
    url = make_url(sync_url)
    if url.drivername.startswith("postgresql"):
        return url.set(drivername="postgresql+asyncpg")
    if url.drivername.startswith("sqlite"):
        return url.set(drivername="sqlite+aiosqlite")
    return url


async_db_url = _make_async_url(settings.database_url)

async_engine_kwargs: dict[str, object] = {
    "pool_pre_ping": True,
    "pool_size": settings.db_pool_size,
    "max_overflow": settings.db_max_overflow,
    "pool_timeout": 30,
    "pool_recycle": settings.db_pool_recycle,
}

async_connect_args: dict[str, object] = {}
if async_db_url.drivername.startswith("postgresql"):
    # asyncpg equivalent of psycopg's prepare_threshold=None: disable statement
    # caching so PgBouncer transaction-mode pooling can't collide prepared
    # statements across backend connections.
    async_connect_args["statement_cache_size"] = 0
    async_connect_args["prepared_statement_cache_size"] = 0
elif async_db_url.drivername.startswith("sqlite"):
    async_connect_args["timeout"] = 30
    # aiosqlite defaults to NullPool, which rejects the QueuePool sizing knobs.
    for _key in ("pool_size", "max_overflow", "pool_timeout", "pool_recycle"):
        async_engine_kwargs.pop(_key, None)

if async_connect_args:
    async_engine_kwargs["connect_args"] = async_connect_args

async_engine = create_async_engine(str(async_db_url), **async_engine_kwargs)

if async_db_url.drivername.startswith("sqlite"):
    @event.listens_for(async_engine.sync_engine, "connect")
    def _configure_async_sqlite(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def get_async_db():
    async with AsyncSessionLocal() as session:
        yield session

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
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

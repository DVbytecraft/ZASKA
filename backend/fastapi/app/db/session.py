from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=30,
    pool_recycle=settings.db_pool_recycle,
    # echo_pool=True,  # uncomment for connection pool debugging
    # PgBouncer transaction-mode pooling can hand a client different backend
    # connections between statements; psycopg3's server-side prepared
    # statements would then collide with statements already prepared by
    # other clients on that backend connection (DuplicatePreparedStatement).
    connect_args={"prepare_threshold": None},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()

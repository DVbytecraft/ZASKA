from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.db.base import Base
from app.models import (  # noqa: F401
    audit_log,
    call_session,
    chat_message,
    dispute,
    feature_flag,
    kyc,
    location_config,
    negotiation_event,
    notification,
    outbox_event,        # was missing — autogenerate ignored OutboxEvent model
    payment_method,
    payout,
    support_ticket,
    task,
    task_application,
    task_completion_code,
    user,
    user_address,
    virtual_card,
    wallet,
    webhook_idempotency,
)

import os

config = context.config

# ALEMBIC_DATABASE_URL overrides DATABASE_URL for migrations.
# Required when DATABASE_URL points to PgBouncer (transaction pool mode):
# PgBouncer does not support DDL (CREATE TABLE, ALTER TABLE) in transaction mode
# because each statement may land on a different connection, breaking multi-statement
# transactions.  Alembic must connect DIRECTLY to PostgreSQL for migrations.
_alembic_url = os.environ.get("ALEMBIC_DATABASE_URL") or settings.database_url
config.set_main_option("sqlalchemy.url", _alembic_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

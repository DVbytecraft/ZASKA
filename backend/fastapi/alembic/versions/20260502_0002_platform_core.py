"""platform core tables and postgis

Revision ID: 20260502_0002
Revises: 20260502_0001
Create Date: 2026-05-02
"""

from alembic import op
import sqlalchemy as sa

revision = "20260502_0002"
down_revision = "20260502_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255)")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(16) DEFAULT 'client' NOT NULL")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE NOT NULL")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW() NOT NULL")
    op.execute("ALTER TABLE users ALTER COLUMN phone DROP NOT NULL")
    op.execute("UPDATE users SET email = CONCAT(phone, '@legacy.local') WHERE email IS NULL")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users(email)")

    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS title VARCHAR(255)")
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS price DOUBLE PRECISION")
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS currency VARCHAR(8)")
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION")
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION")
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS created_by VARCHAR(36)")
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS assigned_to VARCHAR(36)")
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW() NOT NULL")
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS budget")
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS mode")
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS primary_location")
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS additional_zones")
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS payment_method")
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS accepted_by")
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS negotiated_budget")
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS status_new VARCHAR(16)")
    op.execute(
        """UPDATE tasks SET status_new = CASE
            WHEN status IN ('created') THEN 'OPEN'
            WHEN status IN ('accepted') THEN 'ASSIGNED'
            WHEN status IN ('completed') THEN 'COMPLETED'
            ELSE 'OPEN' END
        WHERE status_new IS NULL"""
    )
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS status")
    op.execute("ALTER TABLE tasks RENAME COLUMN status_new TO status")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tasks_latitude ON tasks(latitude)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tasks_longitude ON tasks(longitude)")

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("sender_id", sa.String(length=36), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_chat_messages_task_id", "chat_messages", ["task_id"])
    op.create_index("ix_chat_messages_sender_id", "chat_messages", ["sender_id"])

    op.create_table(
        "countries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("city", sa.String(length=120), nullable=False),
    )
    op.create_table(
        "currencies",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("code", sa.String(length=8), nullable=False, unique=True),
        sa.Column("name", sa.String(length=120), nullable=False),
    )
    op.create_table(
        "payment_methods_config",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("country_id", sa.String(length=36), nullable=False),
        sa.Column("method_name", sa.String(length=100), nullable=False),
    )
    op.create_table(
        "emergency_numbers",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("country_id", sa.String(length=36), nullable=False),
        sa.Column("service_name", sa.String(length=100), nullable=False),
        sa.Column("phone_number", sa.String(length=32), nullable=False),
    )
    op.create_table(
        "feature_flags",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("feature", sa.String(length=100), nullable=False),
        sa.Column("country_id", sa.String(length=36), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("feature", "country_id", name="uq_feature_country"),
    )
    op.create_index("ix_feature_flags_feature", "feature_flags", ["feature"])
    op.create_index("ix_feature_flags_country_id", "feature_flags", ["country_id"])

    op.create_table(
        "kyc_submissions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("id_document_url", sa.String(length=500), nullable=False),
        sa.Column("selfie_url", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_kyc_submissions_user_id", "kyc_submissions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_kyc_submissions_user_id", table_name="kyc_submissions")
    op.drop_table("kyc_submissions")
    op.drop_index("ix_feature_flags_country_id", table_name="feature_flags")
    op.drop_index("ix_feature_flags_feature", table_name="feature_flags")
    op.drop_table("feature_flags")
    op.drop_table("emergency_numbers")
    op.drop_table("payment_methods_config")
    op.drop_table("currencies")
    op.drop_table("countries")
    op.drop_index("ix_chat_messages_sender_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_task_id", table_name="chat_messages")
    op.drop_table("chat_messages")

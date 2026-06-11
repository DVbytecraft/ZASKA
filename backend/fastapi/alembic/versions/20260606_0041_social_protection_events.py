"""social protection events

Revision ID: 20260606_0041
Revises: 20260606_0040
Create Date: 2026-06-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260606_0041"
down_revision = "20260606_0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "social_protection_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("period_key", sa.String(length=7), nullable=False),
        sa.Column("amount", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="completed"),
        sa.Column("reference", sa.String(length=128), nullable=True),
        sa.Column("metadata", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "event_type",
            "period_key",
            "currency",
            name="uq_social_protection_event_scope",
        ),
    )
    op.create_index(
        "ix_social_protection_event_user_created",
        "social_protection_events",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_social_protection_events_currency"),
        "social_protection_events",
        ["currency"],
        unique=False,
    )
    op.create_index(
        op.f("ix_social_protection_events_event_type"),
        "social_protection_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_social_protection_events_period_key"),
        "social_protection_events",
        ["period_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_social_protection_events_reference"),
        "social_protection_events",
        ["reference"],
        unique=False,
    )
    op.create_index(
        op.f("ix_social_protection_events_user_id"),
        "social_protection_events",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_social_protection_events_user_id"), table_name="social_protection_events")
    op.drop_index(op.f("ix_social_protection_events_reference"), table_name="social_protection_events")
    op.drop_index(op.f("ix_social_protection_events_period_key"), table_name="social_protection_events")
    op.drop_index(op.f("ix_social_protection_events_event_type"), table_name="social_protection_events")
    op.drop_index(op.f("ix_social_protection_events_currency"), table_name="social_protection_events")
    op.drop_index("ix_social_protection_event_user_created", table_name="social_protection_events")
    op.drop_table("social_protection_events")

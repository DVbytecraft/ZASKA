"""bidirectional reviews

Revision ID: 20260606_0051
Revises: 20260606_0050
Create Date: 2026-06-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260606_0051"
down_revision = "20260606_0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("client_rating_sum", sa.Float(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("client_rating_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("premium_access_restricted", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("users", sa.Column("premium_access_restricted_reason", sa.String(length=512), nullable=True))
    op.add_column("users", sa.Column("premium_access_restricted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tasks", sa.Column("tasker_rated", sa.Boolean(), nullable=False, server_default="false"))

    op.create_table(
        "user_reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("reviewer_id", sa.String(length=36), nullable=False),
        sa.Column("reviewee_id", sa.String(length=36), nullable=False),
        sa.Column("review_type", sa.String(length=32), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("punctuality_score", sa.Integer(), nullable=True),
        sa.Column("quality_score", sa.Integer(), nullable=True),
        sa.Column("communication_score", sa.Integer(), nullable=True),
        sa.Column("standards_score", sa.Integer(), nullable=True),
        sa.Column("instructions_score", sa.Integer(), nullable=True),
        sa.Column("behavior_score", sa.Integer(), nullable=True),
        sa.Column("payment_score", sa.Integer(), nullable=True),
        sa.Column("comment", sa.String(length=512), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["reviewee_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "review_type", name="uq_user_review_task_type"),
        sa.UniqueConstraint("task_id", "reviewer_id", name="uq_user_review_task_reviewer"),
    )
    op.create_index(op.f("ix_user_reviews_task_id"), "user_reviews", ["task_id"], unique=False)
    op.create_index(op.f("ix_user_reviews_reviewer_id"), "user_reviews", ["reviewer_id"], unique=False)
    op.create_index(op.f("ix_user_reviews_reviewee_id"), "user_reviews", ["reviewee_id"], unique=False)
    op.create_index(op.f("ix_user_reviews_review_type"), "user_reviews", ["review_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_reviews_review_type"), table_name="user_reviews")
    op.drop_index(op.f("ix_user_reviews_reviewee_id"), table_name="user_reviews")
    op.drop_index(op.f("ix_user_reviews_reviewer_id"), table_name="user_reviews")
    op.drop_index(op.f("ix_user_reviews_task_id"), table_name="user_reviews")
    op.drop_table("user_reviews")
    op.drop_column("tasks", "tasker_rated")
    op.drop_column("users", "premium_access_restricted_at")
    op.drop_column("users", "premium_access_restricted_reason")
    op.drop_column("users", "premium_access_restricted")
    op.drop_column("users", "client_rating_count")
    op.drop_column("users", "client_rating_sum")

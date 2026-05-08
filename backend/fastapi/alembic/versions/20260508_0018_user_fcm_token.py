"""users: add fcm_token column for push notifications

Revision ID: 20260508_0018
Revises: 20260508_0017
Create Date: 2026-05-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260508_0018"
down_revision = "20260508_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("fcm_token", sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "fcm_token")

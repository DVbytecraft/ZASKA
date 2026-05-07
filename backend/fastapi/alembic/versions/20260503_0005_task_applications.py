"""task_applications — Choose Mode tasker applications

Revision ID: 20260503_0005
Revises: 20260503_0004
Create Date: 2026-05-03

Crée la table task_applications pour le mode Choose :
  - Un tasker postule sur une tâche OPEN
  - Le client consulte la liste et accepte un candidat
  - Contrainte unique (task_id, tasker_id) — un seul dossier par couple
"""

from alembic import op
import sqlalchemy as sa

revision = "20260503_0005"
down_revision = "20260503_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_applications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("tasker_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("proposed_price", sa.Numeric(20, 6), nullable=True),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("task_id", "tasker_id", name="uq_application_task_tasker"),
    )
    op.create_index("ix_task_applications_task_id", "task_applications", ["task_id"])
    op.create_index("ix_task_applications_tasker_id", "task_applications", ["tasker_id"])


def downgrade() -> None:
    op.drop_table("task_applications")

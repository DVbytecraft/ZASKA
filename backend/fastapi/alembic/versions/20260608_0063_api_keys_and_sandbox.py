"""api keys and sandbox isolation

Revision ID: 20260608_0063
Revises: 20260607_0062
Create Date: 2026-06-08

Crée :
  - api_keys                       : clés API B2B (scopes, sandbox, rate-limit, expiration, révocation)
  - wallets.is_sandbox              + nouvelle contrainte unique (user_id, currency, is_sandbox)
  - transactions.is_sandbox
  - escrows.is_sandbox
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260608_0063"
down_revision = "20260607_0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=255), nullable=False),
        sa.Column("scopes_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("is_sandbox", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["business_organizations.id"], name="fk_api_keys_organization"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name="fk_api_keys_created_by"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_keys_organization_id", "api_keys", ["organization_id"], unique=False)
    op.create_index("ix_api_keys_key_prefix", "api_keys", ["key_prefix"], unique=True)
    op.create_index("ix_api_keys_status", "api_keys", ["status"], unique=False)

    # ── wallets.is_sandbox ────────────────────────────────────────────────
    op.add_column("wallets", sa.Column("is_sandbox", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.drop_constraint("uq_wallet_user_currency", "wallets", type_="unique")
    op.create_unique_constraint("uq_wallet_user_currency_sandbox", "wallets", ["user_id", "currency", "is_sandbox"])

    # ── transactions.is_sandbox ───────────────────────────────────────────
    op.add_column("transactions", sa.Column("is_sandbox", sa.Boolean(), nullable=False, server_default=sa.false()))

    # ── escrows.is_sandbox ────────────────────────────────────────────────
    op.add_column("escrows", sa.Column("is_sandbox", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("escrows", "is_sandbox")
    op.drop_column("transactions", "is_sandbox")

    op.drop_constraint("uq_wallet_user_currency_sandbox", "wallets", type_="unique")
    op.create_unique_constraint("uq_wallet_user_currency", "wallets", ["user_id", "currency"])
    op.drop_column("wallets", "is_sandbox")

    op.drop_index("ix_api_keys_status", table_name="api_keys")
    op.drop_index("ix_api_keys_key_prefix", table_name="api_keys")
    op.drop_index("ix_api_keys_organization_id", table_name="api_keys")
    op.drop_table("api_keys")

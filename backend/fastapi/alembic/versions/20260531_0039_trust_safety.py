"""Trust & Safety: TrustScore, Skills, Badges, PhotoVerification, ModerationCase, user profile fields.

Revision ID: 20260531_0039
Revises: 20260511_0038
Create Date: 2026-05-31
"""

revision = "20260531_0039"
down_revision = "20260511_0038"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    # ── User profile enrichment ───────────────────────────────────────────────
    op.add_column("users", sa.Column("bio", sa.String(512), nullable=True))
    op.add_column("users", sa.Column("city", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("availability", sa.String(32), nullable=True))
    op.add_column("users", sa.Column("hourly_rate", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("response_time", sa.String(32), nullable=True))

    # ── Trust scores ──────────────────────────────────────────────────────────
    op.create_table(
        "trust_scores",
        sa.Column("id",             sa.String(36),  nullable=False),
        sa.Column("user_id",        sa.String(36),  nullable=False),
        sa.Column("total_score",    sa.Float(),     nullable=False, server_default="0"),
        sa.Column("level",          sa.String(16),  nullable=False, server_default="BRONZE"),
        sa.Column("identity_score", sa.Float(),     nullable=False, server_default="0"),
        sa.Column("financial_score",sa.Float(),     nullable=False, server_default="0"),
        sa.Column("profile_score",  sa.Float(),     nullable=False, server_default="0"),
        sa.Column("age_score",      sa.Float(),     nullable=False, server_default="0"),
        sa.Column("community_score",sa.Float(),     nullable=False, server_default="0"),
        sa.Column("behavior_score", sa.Float(),     nullable=False, server_default="0"),
        sa.Column("computed_at",    sa.DateTime(),  nullable=False),
        sa.Column("created_at",     sa.DateTime(),  nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("user_id", name="uq_trust_score_user"),
    )
    op.create_index("ix_trust_scores_user_id", "trust_scores", ["user_id"])

    # ── Skills catalog ────────────────────────────────────────────────────────
    op.create_table(
        "skills",
        sa.Column("id",         sa.String(36),  nullable=False),
        sa.Column("name",       sa.String(64),  nullable=False),
        sa.Column("category",   sa.String(32),  nullable=False, server_default="general"),
        sa.Column("created_at", sa.DateTime(),  nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_skill_name"),
    )

    # ── User skills ───────────────────────────────────────────────────────────
    op.create_table(
        "user_skills",
        sa.Column("id",         sa.String(36),  nullable=False),
        sa.Column("user_id",    sa.String(36),  nullable=False),
        sa.Column("skill_id",   sa.String(36),  nullable=False),
        sa.Column("level",      sa.String(16),  nullable=False, server_default="BEGINNER"),
        sa.Column("created_at", sa.DateTime(),  nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"]),
        sa.UniqueConstraint("user_id", "skill_id", name="uq_user_skill"),
    )
    op.create_index("ix_user_skills_user_id", "user_skills", ["user_id"])

    # ── Badges catalog ────────────────────────────────────────────────────────
    op.create_table(
        "badges",
        sa.Column("id",          sa.String(36),  nullable=False),
        sa.Column("code",        sa.String(32),  nullable=False),
        sa.Column("label",       sa.String(64),  nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("icon",        sa.String(64),  nullable=False, server_default="medal"),
        sa.Column("created_at",  sa.DateTime(),  nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_badge_code"),
    )

    # ── User badges ───────────────────────────────────────────────────────────
    op.create_table(
        "user_badges",
        sa.Column("id",         sa.String(36),  nullable=False),
        sa.Column("user_id",    sa.String(36),  nullable=False),
        sa.Column("badge_code", sa.String(32),  nullable=False),
        sa.Column("awarded_at", sa.DateTime(),  nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("user_id", "badge_code", name="uq_user_badge"),
    )
    op.create_index("ix_user_badges_user_id", "user_badges", ["user_id"])

    # ── Photo verifications ───────────────────────────────────────────────────
    op.create_table(
        "photo_verifications",
        sa.Column("id",              sa.String(36),  nullable=False),
        sa.Column("user_id",         sa.String(36),  nullable=False),
        sa.Column("selfie_url",      sa.String(512), nullable=False),
        sa.Column("status",          sa.String(16),  nullable=False, server_default="PENDING"),
        sa.Column("liveness_score",  sa.Float(),     nullable=True),
        sa.Column("provider",        sa.String(32),  nullable=False, server_default="mock"),
        sa.Column("reviewed_at",     sa.DateTime(),  nullable=True),
        sa.Column("created_at",      sa.DateTime(),  nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("user_id", name="uq_photo_verification_user"),
    )
    op.create_index("ix_photo_verifications_user_id", "photo_verifications", ["user_id"])

    # ── Moderation cases ──────────────────────────────────────────────────────
    op.create_table(
        "moderation_cases",
        sa.Column("id",               sa.String(36),  nullable=False),
        sa.Column("reporter_id",      sa.String(36),  nullable=False),
        sa.Column("reported_user_id", sa.String(36),  nullable=True),
        sa.Column("content_type",     sa.String(32),  nullable=False),
        sa.Column("content_id",       sa.String(36),  nullable=True),
        sa.Column("reason",           sa.String(512), nullable=False),
        sa.Column("ai_analysis",      sa.Text(),      nullable=True),
        sa.Column("severity",         sa.String(16),  nullable=False, server_default="LOW"),
        sa.Column("status",           sa.String(16),  nullable=False, server_default="PENDING"),
        sa.Column("resolution",       sa.String(512), nullable=True),
        sa.Column("action_taken",     sa.String(16),  nullable=False, server_default="none"),
        sa.Column("resolver_id",      sa.String(36),  nullable=True),
        sa.Column("resolved_at",      sa.DateTime(),  nullable=True),
        sa.Column("escalated_at",     sa.DateTime(),  nullable=True),
        sa.Column("created_at",       sa.DateTime(),  nullable=False),
        sa.Column("updated_at",       sa.DateTime(),  nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["reporter_id"],      ["users.id"]),
        sa.ForeignKeyConstraint(["reported_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["resolver_id"],      ["users.id"]),
    )
    op.create_index("ix_moderation_cases_reporter_id",      "moderation_cases", ["reporter_id"])
    op.create_index("ix_moderation_cases_reported_user_id", "moderation_cases", ["reported_user_id"])
    op.create_index("ix_moderation_cases_status",           "moderation_cases", ["status"])


def downgrade() -> None:
    op.drop_table("moderation_cases")
    op.drop_table("photo_verifications")
    op.drop_table("user_badges")
    op.drop_table("badges")
    op.drop_table("user_skills")
    op.drop_table("skills")
    op.drop_table("trust_scores")
    op.drop_column("users", "response_time")
    op.drop_column("users", "hourly_rate")
    op.drop_column("users", "availability")
    op.drop_column("users", "city")
    op.drop_column("users", "bio")

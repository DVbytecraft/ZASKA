"""advanced kyc foundation

Revision ID: 20260607_0056
Revises: 20260607_0055
Create Date: 2026-06-07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260607_0056"
down_revision = "20260607_0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("kyc_submissions", sa.Column("submission_kind", sa.String(length=16), nullable=False, server_default="full"))
    op.add_column("kyc_submissions", sa.Column("id_document_type", sa.String(length=32), nullable=True))
    op.add_column("kyc_submissions", sa.Column("id_document_number_masked", sa.String(length=64), nullable=True))
    op.add_column("kyc_submissions", sa.Column("document_country_code", sa.String(length=2), nullable=True))
    op.add_column("kyc_submissions", sa.Column("biometric_status", sa.String(length=24), nullable=False, server_default="pending"))
    op.add_column("kyc_submissions", sa.Column("face_match_score", sa.Float(), nullable=True))
    op.add_column("kyc_submissions", sa.Column("liveness_score", sa.Float(), nullable=True))
    op.add_column("kyc_submissions", sa.Column("ocr_status", sa.String(length=24), nullable=False, server_default="pending"))
    op.add_column("kyc_submissions", sa.Column("ocr_payload_json", sa.Text(), nullable=True))
    op.add_column("kyc_submissions", sa.Column("criminal_record_issued_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("kyc_submissions", sa.Column("criminal_record_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("kyc_submissions", sa.Column("criminal_record_risk_level", sa.String(length=24), nullable=False, server_default="pending"))
    op.add_column("kyc_submissions", sa.Column("criminal_record_analysis_json", sa.Text(), nullable=True))
    op.add_column("kyc_submissions", sa.Column("renewal_of_submission_id", sa.String(length=36), nullable=True))
    op.add_column("kyc_submissions", sa.Column("metadata_json", sa.Text(), nullable=True))

    op.create_index("ix_kyc_submissions_submission_kind", "kyc_submissions", ["submission_kind"], unique=False)
    op.create_index("ix_kyc_submissions_biometric_status", "kyc_submissions", ["biometric_status"], unique=False)
    op.create_index("ix_kyc_submissions_ocr_status", "kyc_submissions", ["ocr_status"], unique=False)
    op.create_index("ix_kyc_submissions_criminal_record_risk_level", "kyc_submissions", ["criminal_record_risk_level"], unique=False)
    op.create_foreign_key(
        "fk_kyc_submissions_renewal_of_submission_id",
        "kyc_submissions",
        "kyc_submissions",
        ["renewal_of_submission_id"],
        ["id"],
    )

    op.alter_column("kyc_submissions", "submission_kind", server_default=None)
    op.alter_column("kyc_submissions", "biometric_status", server_default=None)
    op.alter_column("kyc_submissions", "ocr_status", server_default=None)
    op.alter_column("kyc_submissions", "criminal_record_risk_level", server_default=None)


def downgrade() -> None:
    op.drop_constraint("fk_kyc_submissions_renewal_of_submission_id", "kyc_submissions", type_="foreignkey")
    op.drop_index("ix_kyc_submissions_criminal_record_risk_level", table_name="kyc_submissions")
    op.drop_index("ix_kyc_submissions_ocr_status", table_name="kyc_submissions")
    op.drop_index("ix_kyc_submissions_biometric_status", table_name="kyc_submissions")
    op.drop_index("ix_kyc_submissions_submission_kind", table_name="kyc_submissions")
    op.drop_column("kyc_submissions", "metadata_json")
    op.drop_column("kyc_submissions", "renewal_of_submission_id")
    op.drop_column("kyc_submissions", "criminal_record_analysis_json")
    op.drop_column("kyc_submissions", "criminal_record_risk_level")
    op.drop_column("kyc_submissions", "criminal_record_expires_at")
    op.drop_column("kyc_submissions", "criminal_record_issued_at")
    op.drop_column("kyc_submissions", "ocr_payload_json")
    op.drop_column("kyc_submissions", "ocr_status")
    op.drop_column("kyc_submissions", "liveness_score")
    op.drop_column("kyc_submissions", "face_match_score")
    op.drop_column("kyc_submissions", "biometric_status")
    op.drop_column("kyc_submissions", "document_country_code")
    op.drop_column("kyc_submissions", "id_document_number_masked")
    op.drop_column("kyc_submissions", "id_document_type")
    op.drop_column("kyc_submissions", "submission_kind")

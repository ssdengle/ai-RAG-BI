"""create bi tables

Revision ID: 20260705_000000
Revises: 20260704_011600
Create Date: 2026-07-05 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260705_000000"
down_revision = "20260704_011600"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_profiles",
        sa.Column("company_id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("industry", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "profile_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_company_profiles_name", "company_profiles", ["name"], unique=True)

    op.create_table(
        "competitor_relationships",
        sa.Column("relationship_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(length=36),
            sa.ForeignKey("company_profiles.company_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "competitor_company_id",
            sa.String(length=36),
            sa.ForeignKey("company_profiles.company_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relationship_type", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_competitor_relationships_company_competitor",
        "competitor_relationships",
        ["company_id", "competitor_company_id"],
        unique=True,
    )
    op.create_index(
        "ix_competitor_relationships_company_id",
        "competitor_relationships",
        ["company_id"],
        unique=False,
    )

    op.create_table(
        "risk_evidence",
        sa.Column("evidence_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(length=36),
            sa.ForeignKey("company_profiles.company_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_id", sa.String(length=64), nullable=False),
        sa.Column("risk_category", sa.String(length=64), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_risk_evidence_company_id", "risk_evidence", ["company_id"], unique=False)
    op.create_index("ix_risk_evidence_risk_category", "risk_evidence", ["risk_category"], unique=False)

    op.create_table(
        "trend_evidence",
        sa.Column("evidence_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(length=36),
            sa.ForeignKey("company_profiles.company_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_id", sa.String(length=64), nullable=False),
        sa.Column("trend_topic", sa.String(length=128), nullable=False),
        sa.Column("document_type", sa.String(length=128), nullable=True),
        sa.Column("document_date", sa.String(length=32), nullable=True),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_trend_evidence_company_id", "trend_evidence", ["company_id"], unique=False)
    op.create_index("ix_trend_evidence_trend_topic", "trend_evidence", ["trend_topic"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_trend_evidence_trend_topic", table_name="trend_evidence")
    op.drop_index("ix_trend_evidence_company_id", table_name="trend_evidence")
    op.drop_table("trend_evidence")
    op.drop_index("ix_risk_evidence_risk_category", table_name="risk_evidence")
    op.drop_index("ix_risk_evidence_company_id", table_name="risk_evidence")
    op.drop_table("risk_evidence")
    op.drop_index("ix_competitor_relationships_company_id", table_name="competitor_relationships")
    op.drop_index("ix_competitor_relationships_company_competitor", table_name="competitor_relationships")
    op.drop_table("competitor_relationships")
    op.drop_index("ix_company_profiles_name", table_name="company_profiles")
    op.drop_table("company_profiles")

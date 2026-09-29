"""create workflow runs table

Revision ID: 20260705_010000
Revises: 20260705_000000
Create Date: 2026-07-05 01:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260705_010000"
down_revision = "20260705_000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_runs",
        sa.Column("workflow_id", sa.String(length=36), primary_key=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("user_request", sa.Text(), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=True),
        sa.Column("topic", sa.String(length=500), nullable=False),
        sa.Column("plan", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("completed_steps", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("failed_steps", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("state_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("trace_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("human_review_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("final_output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_workflow_runs_status", "workflow_runs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_workflow_runs_status", table_name="workflow_runs")
    op.drop_table("workflow_runs")

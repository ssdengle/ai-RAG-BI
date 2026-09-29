"""create evaluation tables

Revision ID: 20260705_020000
Revises: 20260705_010000
Create Date: 2026-07-05 02:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260705_020000"
down_revision = "20260705_010000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "benchmark_datasets",
        sa.Column("dataset_id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False, server_default="1.0"),
        sa.Column("dataset_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_benchmark_datasets_name", "benchmark_datasets", ["name"], unique=False)
    op.create_index("ix_benchmark_datasets_target_type", "benchmark_datasets", ["target_type"], unique=False)

    op.create_table(
        "evaluation_test_cases",
        sa.Column("test_case_id", sa.String(length=36), primary_key=True),
        sa.Column("dataset_id", sa.String(length=36), sa.ForeignKey("benchmark_datasets.dataset_id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("input_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("expected_answer_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("source_documents_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("rubric_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_evaluation_test_cases_dataset_id", "evaluation_test_cases", ["dataset_id"], unique=False)

    op.create_table(
        "evaluation_runs",
        sa.Column("run_id", sa.String(length=36), primary_key=True),
        sa.Column("dataset_id", sa.String(length=36), sa.ForeignKey("benchmark_datasets.dataset_id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("baseline_run_id", sa.String(length=36), nullable=True),
        sa.Column("llm_provider", sa.String(length=100), nullable=True),
        sa.Column("llm_model", sa.String(length=255), nullable=True),
        sa.Column("summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_evaluation_runs_dataset_id", "evaluation_runs", ["dataset_id"], unique=False)
    op.create_index("ix_evaluation_runs_status", "evaluation_runs", ["status"], unique=False)
    op.create_index("ix_evaluation_runs_baseline_run_id", "evaluation_runs", ["baseline_run_id"], unique=False)

    op.create_table(
        "evaluation_results",
        sa.Column("result_id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("evaluation_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("test_case_id", sa.String(length=36), nullable=False),
        sa.Column("test_case_name", sa.String(length=255), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("overall_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("scorer_results_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("failure_modes_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("actual_output_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("token_usage_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_evaluation_results_run_id", "evaluation_results", ["run_id"], unique=False)
    op.create_index("ix_evaluation_results_test_case_id", "evaluation_results", ["test_case_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_evaluation_results_test_case_id", table_name="evaluation_results")
    op.drop_index("ix_evaluation_results_run_id", table_name="evaluation_results")
    op.drop_table("evaluation_results")
    op.drop_index("ix_evaluation_runs_baseline_run_id", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_status", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_dataset_id", table_name="evaluation_runs")
    op.drop_table("evaluation_runs")
    op.drop_index("ix_evaluation_test_cases_dataset_id", table_name="evaluation_test_cases")
    op.drop_table("evaluation_test_cases")
    op.drop_index("ix_benchmark_datasets_target_type", table_name="benchmark_datasets")
    op.drop_index("ix_benchmark_datasets_name", table_name="benchmark_datasets")
    op.drop_table("benchmark_datasets")

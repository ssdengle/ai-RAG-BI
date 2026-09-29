from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from apps.api.app.core.errors import DomainError
from apps.api.app.domain.evaluation import (
    BenchmarkDataset,
    EvaluationResult,
    EvaluationRun,
    EvaluationRunStatus,
    EvaluationTargetType,
    FailureMode,
    ScorerResult,
)
from apps.api.app.services.evaluation_report_service import EvaluationReportService


NOW = datetime.now(timezone.utc)


class _FakeEvaluationRepository:
    def __init__(self) -> None:
        self.datasets = {
            "dataset-1": BenchmarkDataset(
                dataset_id="dataset-1",
                name="QA Benchmark",
                description="",
                target_type=EvaluationTargetType.GROUNDED_QA,
                version="1.0",
                metadata={},
                created_at=NOW,
                updated_at=NOW,
            )
        }
        self.runs = {
            "run-current": EvaluationRun(
                run_id="run-current",
                dataset_id="dataset-1",
                status=EvaluationRunStatus.COMPLETED,
                target_type=EvaluationTargetType.GROUNDED_QA,
                config={},
                baseline_run_id="run-baseline",
                llm_provider="openai",
                llm_model="gpt-4o-mini",
                summary={
                    "total_test_cases": 2,
                    "passed_test_cases": 1,
                    "failed_test_cases": 1,
                    "average_score": 0.75,
                    "pass_rate": 0.5,
                    "failure_mode_summary": {"low_accuracy": 1},
                },
                error_message=None,
                created_at=NOW,
                updated_at=NOW,
                started_at=NOW,
                completed_at=NOW,
            ),
            "run-baseline": EvaluationRun(
                run_id="run-baseline",
                dataset_id="dataset-1",
                status=EvaluationRunStatus.COMPLETED,
                target_type=EvaluationTargetType.GROUNDED_QA,
                config={},
                baseline_run_id=None,
                llm_provider="openai",
                llm_model="gpt-4o-mini",
                summary={
                    "total_test_cases": 2,
                    "passed_test_cases": 2,
                    "failed_test_cases": 0,
                    "average_score": 0.9,
                    "pass_rate": 1.0,
                    "failure_mode_summary": {},
                },
                error_message=None,
                created_at=NOW,
                updated_at=NOW,
                started_at=NOW,
                completed_at=NOW,
            ),
        }
        self.results = {
            "run-current": [
                EvaluationResult(
                    result_id=str(uuid4()),
                    run_id="run-current",
                    test_case_id="tc-1",
                    test_case_name="Passing case",
                    passed=True,
                    overall_score=0.9,
                    scorer_results=[
                        ScorerResult(scorer="answer_accuracy", score=0.9, passed=True),
                        ScorerResult(scorer="latency", score=1.0, passed=True),
                    ],
                    failure_modes=[],
                    actual_output={},
                    latency_ms=100.0,
                    token_usage={},
                    error_message=None,
                    created_at=NOW,
                ),
                EvaluationResult(
                    result_id=str(uuid4()),
                    run_id="run-current",
                    test_case_id="tc-2",
                    test_case_name="Failing case",
                    passed=False,
                    overall_score=0.6,
                    scorer_results=[
                        ScorerResult(scorer="answer_accuracy", score=0.6, passed=False),
                    ],
                    failure_modes=[FailureMode.LOW_ACCURACY],
                    actual_output={},
                    latency_ms=200.0,
                    token_usage={},
                    error_message=None,
                    created_at=NOW,
                ),
            ],
            "run-baseline": [
                EvaluationResult(
                    result_id=str(uuid4()),
                    run_id="run-baseline",
                    test_case_id="tc-1",
                    test_case_name="Passing case",
                    passed=True,
                    overall_score=0.95,
                    scorer_results=[ScorerResult(scorer="answer_accuracy", score=0.95, passed=True)],
                    failure_modes=[],
                    actual_output={},
                    latency_ms=90.0,
                    token_usage={},
                    error_message=None,
                    created_at=NOW,
                ),
                EvaluationResult(
                    result_id=str(uuid4()),
                    run_id="run-baseline",
                    test_case_id="tc-2",
                    test_case_name="Failing case",
                    passed=True,
                    overall_score=0.85,
                    scorer_results=[ScorerResult(scorer="answer_accuracy", score=0.85, passed=True)],
                    failure_modes=[],
                    actual_output={},
                    latency_ms=95.0,
                    token_usage={},
                    error_message=None,
                    created_at=NOW,
                ),
            ],
        }

    async def get_run(self, session, run_id):
        return self.runs.get(run_id)

    async def get_dataset(self, session, dataset_id):
        return self.datasets.get(dataset_id)

    async def list_results(self, session, *, run_id):
        return self.results.get(run_id, [])


def test_report_generation_includes_failed_cases_and_regression() -> None:
    service = EvaluationReportService(evaluation_repository=_FakeEvaluationRepository())

    report = asyncio.run(service.generate_report(None, run_id="run-current"))

    assert report.passed is False
    assert report.average_score == 0.75
    assert len(report.failed_test_cases) == 1
    assert report.failure_mode_summary["low_accuracy"] == 1
    assert report.model_comparison.provider == "openai"
    assert report.regression_comparison.baseline_run_id == "run-baseline"
    assert report.regression_comparison.score_delta == pytest.approx(-0.15)
    assert "tc-2" in report.regression_comparison.regressed_test_cases
    assert "answer_accuracy" in report.scorer_averages


def test_report_generation_raises_for_missing_run() -> None:
    service = EvaluationReportService(evaluation_repository=_FakeEvaluationRepository())

    with pytest.raises(DomainError) as exc_info:
        asyncio.run(service.generate_report(None, run_id="missing"))

    assert exc_info.value.code == "evaluation_run_not_found"

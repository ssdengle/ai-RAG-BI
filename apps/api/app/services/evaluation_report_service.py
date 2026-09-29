from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.core.errors import DomainError
from apps.api.app.domain.evaluation import (
    EvaluationReport,
    EvaluationRunStatus,
    FailedTestCaseSummary,
    ModelComparisonField,
    RegressionComparisonField,
)
from apps.api.app.repositories.evaluation_repository import EvaluationRepository


class EvaluationReportService:
    def __init__(self, *, evaluation_repository: EvaluationRepository) -> None:
        self._evaluation_repository = evaluation_repository

    async def generate_report(self, session: AsyncSession, *, run_id: str) -> EvaluationReport:
        run = await self._evaluation_repository.get_run(session, run_id)
        if run is None:
            raise DomainError(
                "Evaluation run was not found.",
                details=run_id,
                code="evaluation_run_not_found",
                status_code=404,
            )

        dataset = await self._evaluation_repository.get_dataset(session, run.dataset_id)
        if dataset is None:
            raise DomainError(
                "Benchmark dataset was not found.",
                details=run.dataset_id,
                code="dataset_not_found",
                status_code=404,
            )

        results = await self._evaluation_repository.list_results(session, run_id=run_id)
        summary = run.summary or {}
        total = int(summary.get("total_test_cases", len(results)))
        passed_count = int(summary.get("passed_test_cases", sum(1 for item in results if item.passed)))
        average_score = float(summary.get("average_score", 0.0))
        pass_rate = float(summary.get("pass_rate", 0.0))
        failure_mode_summary = dict(summary.get("failure_mode_summary", {}))

        failed_cases = [
            FailedTestCaseSummary(
                test_case_id=result.test_case_id,
                test_case_name=result.test_case_name,
                overall_score=result.overall_score,
                failure_modes=[mode.value for mode in result.failure_modes],
                error_message=result.error_message,
            )
            for result in results
            if not result.passed
        ]

        scorer_averages = _compute_scorer_averages(results)
        model_comparison = ModelComparisonField(
            provider=run.llm_provider,
            model=run.llm_model,
            average_score=average_score,
            pass_rate=pass_rate,
            total_test_cases=total,
        )
        regression_comparison = await self._build_regression_comparison(
            session,
            run_id=run_id,
            baseline_run_id=run.baseline_run_id,
            current_average_score=average_score,
            current_pass_rate=pass_rate,
            results=results,
        )

        return EvaluationReport(
            run_id=run.run_id,
            dataset_id=run.dataset_id,
            dataset_name=dataset.name,
            target_type=run.target_type,
            status=run.status,
            passed=total > 0 and passed_count == total,
            average_score=average_score,
            pass_rate=pass_rate,
            total_test_cases=total,
            passed_test_cases=passed_count,
            failed_test_cases=failed_cases,
            failure_mode_summary=failure_mode_summary,
            model_comparison=model_comparison,
            regression_comparison=regression_comparison,
            scorer_averages=scorer_averages,
            created_at=run.created_at,
            completed_at=run.completed_at,
        )

    async def _build_regression_comparison(
        self,
        session: AsyncSession,
        *,
        run_id: str,
        baseline_run_id: str | None,
        current_average_score: float,
        current_pass_rate: float,
        results,
    ) -> RegressionComparisonField:
        if baseline_run_id is None:
            return RegressionComparisonField(
                baseline_run_id=None,
                current_average_score=current_average_score,
                baseline_average_score=None,
                score_delta=None,
                pass_rate_delta=None,
                regressed_test_cases=[],
            )

        baseline_run = await self._evaluation_repository.get_run(session, baseline_run_id)
        if baseline_run is None:
            return RegressionComparisonField(
                baseline_run_id=baseline_run_id,
                current_average_score=current_average_score,
                baseline_average_score=None,
                score_delta=None,
                pass_rate_delta=None,
                regressed_test_cases=[],
            )

        baseline_summary = baseline_run.summary or {}
        baseline_average = float(baseline_summary.get("average_score", 0.0))
        baseline_pass_rate = float(baseline_summary.get("pass_rate", 0.0))
        baseline_results = await self._evaluation_repository.list_results(session, run_id=baseline_run_id)
        baseline_by_case = {item.test_case_id: item for item in baseline_results}
        regressed: list[str] = []
        for result in results:
            baseline_result = baseline_by_case.get(result.test_case_id)
            if baseline_result is None:
                continue
            if result.overall_score < baseline_result.overall_score or (
                baseline_result.passed and not result.passed
            ):
                regressed.append(result.test_case_id)

        return RegressionComparisonField(
            baseline_run_id=baseline_run_id,
            current_average_score=current_average_score,
            baseline_average_score=baseline_average,
            score_delta=round(current_average_score - baseline_average, 4),
            pass_rate_delta=round(current_pass_rate - baseline_pass_rate, 4),
            regressed_test_cases=regressed,
        )


def _compute_scorer_averages(results) -> dict[str, float]:
    totals: dict[str, float] = {}
    counts: dict[str, int] = {}
    for result in results:
        for scorer_result in result.scorer_results:
            totals[scorer_result.scorer] = totals.get(scorer_result.scorer, 0.0) + scorer_result.score
            counts[scorer_result.scorer] = counts.get(scorer_result.scorer, 0) + 1
    return {
        scorer: round(totals[scorer] / counts[scorer], 4)
        for scorer in totals
        if counts.get(scorer, 0) > 0
    }

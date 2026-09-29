from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.domain.evaluation import (
    BenchmarkDataset,
    EvaluationResult,
    EvaluationRun,
    EvaluationRunStatus,
    EvaluationTargetType,
    EvaluationTestCase,
    ExpectedAnswer,
    FailureMode,
    ScorerResult,
    ScoringRubric,
    SourceDocument,
)
from apps.api.app.repositories.models import (
    BenchmarkDatasetModel,
    EvaluationResultModel,
    EvaluationRunModel,
    EvaluationTestCaseModel,
)


class EvaluationRepository:
    async def create_dataset(
        self,
        session: AsyncSession,
        *,
        name: str,
        description: str,
        target_type: EvaluationTargetType,
        version: str = "1.0",
        metadata: dict[str, Any] | None = None,
    ) -> BenchmarkDataset:
        model = BenchmarkDatasetModel(
            dataset_id=str(uuid4()),
            name=name,
            description=description,
            target_type=target_type.value,
            version=version,
            dataset_metadata=metadata or {},
        )
        session.add(model)
        await session.flush()
        await session.refresh(model)
        return _to_dataset(model)

    async def list_datasets(self, session: AsyncSession) -> list[BenchmarkDataset]:
        result = await session.execute(
            select(BenchmarkDatasetModel).order_by(BenchmarkDatasetModel.created_at.desc())
        )
        return [_to_dataset(model) for model in result.scalars().all()]

    async def get_dataset(self, session: AsyncSession, dataset_id: str) -> BenchmarkDataset | None:
        model = await session.get(BenchmarkDatasetModel, dataset_id)
        if model is None:
            return None
        return _to_dataset(model)

    async def create_test_case(
        self,
        session: AsyncSession,
        *,
        dataset_id: str,
        name: str,
        query: str,
        expected_answer: ExpectedAnswer,
        source_documents: list[SourceDocument] | None = None,
        rubric: ScoringRubric | None = None,
        input_payload: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> EvaluationTestCase:
        model = EvaluationTestCaseModel(
            test_case_id=str(uuid4()),
            dataset_id=dataset_id,
            name=name,
            query=query,
            input_payload=input_payload or {},
            expected_answer_json=_expected_answer_to_dict(expected_answer),
            source_documents_json=[_source_document_to_dict(doc) for doc in (source_documents or [])],
            rubric_json=_rubric_to_dict(rubric or ScoringRubric()),
            tags=tags or [],
        )
        session.add(model)
        await session.flush()
        await session.refresh(model)
        return _to_test_case(model)

    async def list_test_cases(self, session: AsyncSession, *, dataset_id: str) -> list[EvaluationTestCase]:
        result = await session.execute(
            select(EvaluationTestCaseModel)
            .where(EvaluationTestCaseModel.dataset_id == dataset_id)
            .order_by(EvaluationTestCaseModel.created_at.asc())
        )
        return [_to_test_case(model) for model in result.scalars().all()]

    async def get_test_case(self, session: AsyncSession, test_case_id: str) -> EvaluationTestCase | None:
        model = await session.get(EvaluationTestCaseModel, test_case_id)
        if model is None:
            return None
        return _to_test_case(model)

    async def create_run(
        self,
        session: AsyncSession,
        *,
        dataset_id: str,
        target_type: EvaluationTargetType,
        config: dict[str, Any],
        baseline_run_id: str | None = None,
    ) -> EvaluationRun:
        now = datetime.now(timezone.utc)
        model = EvaluationRunModel(
            run_id=str(uuid4()),
            dataset_id=dataset_id,
            status=EvaluationRunStatus.PENDING.value,
            target_type=target_type.value,
            config_json=config,
            baseline_run_id=baseline_run_id,
            llm_provider=None,
            llm_model=None,
            summary_json={},
            error_message=None,
            started_at=None,
            completed_at=None,
        )
        session.add(model)
        await session.flush()
        await session.refresh(model)
        return _to_run(model)

    async def save_run(self, session: AsyncSession, run: EvaluationRun) -> EvaluationRun:
        model = await session.get(EvaluationRunModel, run.run_id)
        if model is None:
            raise KeyError(run.run_id)

        model.status = run.status.value
        model.config_json = run.config
        model.baseline_run_id = run.baseline_run_id
        model.llm_provider = run.llm_provider
        model.llm_model = run.llm_model
        model.summary_json = run.summary
        model.error_message = run.error_message
        model.started_at = run.started_at
        model.completed_at = run.completed_at
        await session.flush()
        await session.refresh(model)
        return _to_run(model)

    async def get_run(self, session: AsyncSession, run_id: str) -> EvaluationRun | None:
        model = await session.get(EvaluationRunModel, run_id)
        if model is None:
            return None
        return _to_run(model)

    async def list_runs(self, session: AsyncSession, *, dataset_id: str | None = None) -> list[EvaluationRun]:
        query = select(EvaluationRunModel).order_by(EvaluationRunModel.created_at.desc())
        if dataset_id is not None:
            query = query.where(EvaluationRunModel.dataset_id == dataset_id)
        result = await session.execute(query)
        return [_to_run(model) for model in result.scalars().all()]

    async def save_result(self, session: AsyncSession, result: EvaluationResult) -> EvaluationResult:
        model = EvaluationResultModel(
            result_id=result.result_id,
            run_id=result.run_id,
            test_case_id=result.test_case_id,
            test_case_name=result.test_case_name,
            passed=result.passed,
            overall_score=result.overall_score,
            scorer_results_json=[_scorer_result_to_dict(item) for item in result.scorer_results],
            failure_modes_json=[mode.value for mode in result.failure_modes],
            actual_output_json=result.actual_output,
            latency_ms=result.latency_ms,
            token_usage_json=result.token_usage,
            error_message=result.error_message,
        )
        session.add(model)
        await session.flush()
        await session.refresh(model)
        return _to_result(model)

    async def list_results(self, session: AsyncSession, *, run_id: str) -> list[EvaluationResult]:
        result = await session.execute(
            select(EvaluationResultModel)
            .where(EvaluationResultModel.run_id == run_id)
            .order_by(EvaluationResultModel.created_at.asc())
        )
        return [_to_result(model) for model in result.scalars().all()]


def _to_dataset(model: BenchmarkDatasetModel) -> BenchmarkDataset:
    return BenchmarkDataset(
        dataset_id=model.dataset_id,
        name=model.name,
        description=model.description,
        target_type=EvaluationTargetType(model.target_type),
        version=model.version,
        metadata=dict(model.dataset_metadata or {}),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_test_case(model: EvaluationTestCaseModel) -> EvaluationTestCase:
    expected = model.expected_answer_json or {}
    rubric = model.rubric_json or {}
    return EvaluationTestCase(
        test_case_id=model.test_case_id,
        dataset_id=model.dataset_id,
        name=model.name,
        query=model.query,
        input_payload=dict(model.input_payload or {}),
        expected_answer=ExpectedAnswer(
            text=str(expected.get("text", "")),
            required_citations=list(expected.get("required_citations") or []),
            required_keywords=list(expected.get("required_keywords") or []),
            min_confidence=expected.get("min_confidence"),
        ),
        source_documents=[
            SourceDocument(
                document_id=str(item.get("document_id", "")),
                title=item.get("title"),
                chunk_ids=list(item.get("chunk_ids") or []),
            )
            for item in (model.source_documents_json or [])
        ],
        rubric=ScoringRubric(
            pass_threshold=float(rubric.get("pass_threshold", 0.7)),
            scorer_weights=dict(rubric.get("scorer_weights") or {}),
            scorer_thresholds=dict(rubric.get("scorer_thresholds") or {}),
            enabled_scorers=list(rubric.get("enabled_scorers") or []),
        ),
        tags=list(model.tags or []),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_run(model: EvaluationRunModel) -> EvaluationRun:
    return EvaluationRun(
        run_id=model.run_id,
        dataset_id=model.dataset_id,
        status=EvaluationRunStatus(model.status),
        target_type=EvaluationTargetType(model.target_type),
        config=dict(model.config_json or {}),
        baseline_run_id=model.baseline_run_id,
        llm_provider=model.llm_provider,
        llm_model=model.llm_model,
        summary=dict(model.summary_json or {}),
        error_message=model.error_message,
        created_at=model.created_at,
        updated_at=model.updated_at,
        started_at=model.started_at,
        completed_at=model.completed_at,
    )


def _to_result(model: EvaluationResultModel) -> EvaluationResult:
    return EvaluationResult(
        result_id=model.result_id,
        run_id=model.run_id,
        test_case_id=model.test_case_id,
        test_case_name=model.test_case_name,
        passed=bool(model.passed),
        overall_score=float(model.overall_score),
        scorer_results=[
            ScorerResult(
                scorer=str(item.get("scorer", "")),
                score=float(item.get("score", 0.0)),
                passed=bool(item.get("passed", False)),
                details=dict(item.get("details") or {}),
            )
            for item in (model.scorer_results_json or [])
        ],
        failure_modes=[FailureMode(mode) for mode in (model.failure_modes_json or [])],
        actual_output=dict(model.actual_output_json or {}),
        latency_ms=model.latency_ms,
        token_usage=dict(model.token_usage_json or {}),
        error_message=model.error_message,
        created_at=model.created_at,
    )


def _expected_answer_to_dict(expected: ExpectedAnswer) -> dict[str, Any]:
    return {
        "text": expected.text,
        "required_citations": expected.required_citations,
        "required_keywords": expected.required_keywords,
        "min_confidence": expected.min_confidence,
    }


def _source_document_to_dict(document: SourceDocument) -> dict[str, Any]:
    return {
        "document_id": document.document_id,
        "title": document.title,
        "chunk_ids": document.chunk_ids,
    }


def _rubric_to_dict(rubric: ScoringRubric) -> dict[str, Any]:
    return {
        "pass_threshold": rubric.pass_threshold,
        "scorer_weights": rubric.scorer_weights,
        "scorer_thresholds": rubric.scorer_thresholds,
        "enabled_scorers": rubric.enabled_scorers,
    }


def _scorer_result_to_dict(result: ScorerResult) -> dict[str, Any]:
    return {
        "scorer": result.scorer,
        "score": result.score,
        "passed": result.passed,
        "details": result.details,
    }

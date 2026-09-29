from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.domain.evaluation import (
    DEFAULT_SCORERS,
    EvaluationExecutionContext,
    EvaluationResult,
    EvaluationRun,
    EvaluationRunStatus,
    EvaluationTargetType,
    EvaluationTestCase,
    FailureMode,
    RunEvaluationConfig,
    ScorerResult,
)
from apps.api.app.domain.retrieval import Citation, RetrievalFilters, RetrievalMode
from apps.api.app.evaluation.judge import HeuristicEvaluationJudge
from apps.api.app.evaluation.scorers import ScorerContext, ScorerRegistry, build_default_scorer_registry
from apps.api.app.repositories.evaluation_repository import EvaluationRepository
from apps.api.app.services.executive_brief_service import ExecutiveBriefService
from apps.api.app.services.question_answering_service import QuestionAnsweringService
from apps.api.app.services.retrieval_service import RetrievalService
from apps.api.app.services.workflow_service import WorkflowService


FAILURE_MODE_BY_SCORER = {
    "answer_accuracy": FailureMode.LOW_ACCURACY,
    "groundedness": FailureMode.UNGROUNDED,
    "citation_correctness": FailureMode.BAD_CITATIONS,
    "hallucination_risk": FailureMode.HALLUCINATION,
    "completeness": FailureMode.INCOMPLETE,
    "relevance": FailureMode.IRRELEVANT,
    "confidence_calibration": FailureMode.CONFIDENCE_MISCALIBRATION,
    "latency": FailureMode.HIGH_LATENCY,
    "cost": FailureMode.HIGH_COST,
}


class EvaluationRunnerService:
    def __init__(
        self,
        *,
        evaluation_repository: EvaluationRepository,
        retrieval_service: RetrievalService,
        question_answering_service: QuestionAnsweringService,
        executive_brief_service: ExecutiveBriefService,
        workflow_service: WorkflowService,
        scorer_registry: ScorerRegistry | None = None,
    ) -> None:
        self._evaluation_repository = evaluation_repository
        self._retrieval_service = retrieval_service
        self._question_answering_service = question_answering_service
        self._executive_brief_service = executive_brief_service
        self._workflow_service = workflow_service
        self._scorer_registry = scorer_registry

    async def run_evaluation(
        self,
        session: AsyncSession,
        *,
        dataset_id: str,
        config: RunEvaluationConfig | None = None,
        baseline_run_id: str | None = None,
    ) -> EvaluationRun:
        dataset = await self._evaluation_repository.get_dataset(session, dataset_id)
        if dataset is None:
            from apps.api.app.core.errors import DomainError

            raise DomainError(
                "Benchmark dataset was not found.",
                details=dataset_id,
                code="dataset_not_found",
                status_code=404,
            )

        resolved_config = config or RunEvaluationConfig()
        try:
            run = await self._evaluation_repository.create_run(
                session,
                dataset_id=dataset_id,
                target_type=dataset.target_type,
                config=_config_to_dict(resolved_config),
                baseline_run_id=baseline_run_id,
            )
            run = await self._mark_run_started(run)
            await self._evaluation_repository.save_run(session, run)

            test_cases = await self._evaluation_repository.list_test_cases(session, dataset_id=dataset_id)
            registry = self._scorer_registry or build_default_scorer_registry(HeuristicEvaluationJudge())

            results: list[EvaluationResult] = []
            for test_case in test_cases:
                result = await self._evaluate_test_case(
                    session,
                    run=run,
                    test_case=test_case,
                    config=resolved_config,
                    registry=registry,
                )
                saved = await self._evaluation_repository.save_result(session, result)
                results.append(saved)

            summary = _build_run_summary(results)
            completed = await self._mark_run_completed(
                run,
                summary=summary,
                llm_provider=_resolve_provider(results),
                llm_model=_resolve_model(results),
            )
            await self._evaluation_repository.save_run(session, completed)
            await session.commit()
            return completed
        except Exception:
            await session.rollback()
            raise

    async def _evaluate_test_case(
        self,
        session: AsyncSession,
        *,
        run: EvaluationRun,
        test_case: EvaluationTestCase,
        config: RunEvaluationConfig,
        registry: ScorerRegistry,
    ) -> EvaluationResult:
        try:
            execution = await self._execute_target(session, run.target_type, test_case, config)
        except Exception as exc:
            execution = EvaluationExecutionContext(
                answer="",
                citations=[],
                confidence=None,
                retrieved_chunk_ids=[],
                latency_ms=0.0,
                llm_provider=None,
                llm_model=None,
                prompt_tokens=None,
                completion_tokens=None,
                total_cost_usd=None,
                raw_output={},
                error_message=str(exc),
            )

        if execution.error_message:
            return EvaluationResult(
                result_id=str(uuid4()),
                run_id=run.run_id,
                test_case_id=test_case.test_case_id,
                test_case_name=test_case.name,
                passed=False,
                overall_score=0.0,
                scorer_results=[],
                failure_modes=[FailureMode.SERVICE_ERROR],
                actual_output=execution.raw_output,
                latency_ms=execution.latency_ms,
                token_usage=_token_usage_dict(execution),
                error_message=execution.error_message,
                created_at=run.started_at or run.created_at,
            )

        if not execution.answer.strip():
            return EvaluationResult(
                result_id=str(uuid4()),
                run_id=run.run_id,
                test_case_id=test_case.test_case_id,
                test_case_name=test_case.name,
                passed=False,
                overall_score=0.0,
                scorer_results=[],
                failure_modes=[FailureMode.EMPTY_RESPONSE],
                actual_output=execution.raw_output,
                latency_ms=execution.latency_ms,
                token_usage=_token_usage_dict(execution),
                error_message=None,
                created_at=run.started_at or run.created_at,
            )

        enabled_scorers = test_case.rubric.enabled_scorers or config.enabled_scorers or list(DEFAULT_SCORERS)
        scorer_results = await self._score_test_case(
            test_case=test_case,
            execution=execution,
            config=config,
            registry=registry,
            enabled_scorers=enabled_scorers,
        )
        overall_score = _weighted_overall_score(scorer_results, test_case)
        pass_threshold = test_case.rubric.pass_threshold or config.pass_threshold
        passed = overall_score >= pass_threshold and all(result.passed for result in scorer_results)
        failure_modes = _derive_failure_modes(scorer_results)

        return EvaluationResult(
            result_id=str(uuid4()),
            run_id=run.run_id,
            test_case_id=test_case.test_case_id,
            test_case_name=test_case.name,
            passed=passed,
            overall_score=overall_score,
            scorer_results=scorer_results,
            failure_modes=failure_modes,
            actual_output=execution.raw_output,
            latency_ms=execution.latency_ms,
            token_usage=_token_usage_dict(execution),
            error_message=None,
            created_at=run.started_at or run.created_at,
        )

    async def _execute_target(
        self,
        session: AsyncSession,
        target_type: EvaluationTargetType,
        test_case: EvaluationTestCase,
        config: RunEvaluationConfig,
    ) -> EvaluationExecutionContext:
        if target_type == EvaluationTargetType.RETRIEVAL:
            return await self._run_retrieval(session, test_case, config)
        if target_type == EvaluationTargetType.GROUNDED_QA:
            return await self._run_grounded_qa(session, test_case, config)
        if target_type == EvaluationTargetType.EXECUTIVE_BRIEF:
            return await self._run_executive_brief(session, test_case, config)
        if target_type == EvaluationTargetType.WORKFLOW:
            return await self._run_workflow(session, test_case, config)
        raise ValueError(f"Unsupported evaluation target: {target_type}")

    async def _run_retrieval(
        self,
        session: AsyncSession,
        test_case: EvaluationTestCase,
        config: RunEvaluationConfig,
    ) -> EvaluationExecutionContext:
        started = time.perf_counter()
        mode: RetrievalMode = test_case.input_payload.get("mode", config.mode)
        top_k = int(test_case.input_payload.get("top_k", config.top_k))
        filters = _build_filters(test_case, config)
        result = await self._retrieval_service.retrieve(
            session,
            query=test_case.query,
            mode=mode,
            filters=filters,
            top_k=top_k,
        )
        latency_ms = (time.perf_counter() - started) * 1000
        answer = " ".join(chunk.text for chunk in result.chunks[:3])
        return EvaluationExecutionContext(
            answer=answer,
            citations=result.citations,
            confidence=_average_score(result.chunks),
            retrieved_chunk_ids=[chunk.chunk_id for chunk in result.chunks],
            latency_ms=latency_ms,
            llm_provider=None,
            llm_model=None,
            prompt_tokens=None,
            completion_tokens=None,
            total_cost_usd=None,
            raw_output={
                "mode": result.mode,
                "query": result.query,
                "chunk_count": len(result.chunks),
                "citations": [_citation_to_dict(citation) for citation in result.citations],
            },
        )

    async def _run_grounded_qa(
        self,
        session: AsyncSession,
        test_case: EvaluationTestCase,
        config: RunEvaluationConfig,
    ) -> EvaluationExecutionContext:
        started = time.perf_counter()
        mode: RetrievalMode = test_case.input_payload.get("mode", config.mode)
        top_k = int(test_case.input_payload.get("top_k", config.top_k))
        filters = _build_filters(test_case, config)
        result = await self._question_answering_service.answer(
            session,
            question=test_case.query,
            mode=mode,
            filters=filters,
            top_k=top_k,
        )
        latency_ms = (time.perf_counter() - started) * 1000
        return EvaluationExecutionContext(
            answer=result.answer,
            citations=result.citations,
            confidence=result.confidence,
            retrieved_chunk_ids=[chunk.chunk_id for chunk in result.retrieval.chunks],
            latency_ms=latency_ms,
            llm_provider=result.llm_provider,
            llm_model=result.llm_model,
            prompt_tokens=None,
            completion_tokens=None,
            total_cost_usd=None,
            raw_output={
                "answer": result.answer,
                "confidence": result.confidence,
                "citations": [_citation_to_dict(citation) for citation in result.citations],
            },
        )

    async def _run_executive_brief(
        self,
        session: AsyncSession,
        test_case: EvaluationTestCase,
        config: RunEvaluationConfig,
    ) -> EvaluationExecutionContext:
        started = time.perf_counter()
        topic = str(test_case.input_payload.get("topic", test_case.query))
        company_id = test_case.input_payload.get("company_id", config.company_id)
        mode: RetrievalMode = test_case.input_payload.get("mode", config.mode)
        top_k = int(test_case.input_payload.get("top_k", config.top_k))
        brief = await self._executive_brief_service.generate_executive_brief(
            session,
            topic=topic,
            company_id=company_id,
            mode=mode,
            top_k=top_k,
        )
        latency_ms = (time.perf_counter() - started) * 1000
        return EvaluationExecutionContext(
            answer=brief.summary,
            citations=brief.citations,
            confidence=brief.confidence,
            retrieved_chunk_ids=[citation.chunk_id for citation in brief.citations],
            latency_ms=latency_ms,
            llm_provider=brief.llm_provider,
            llm_model=brief.llm_model,
            prompt_tokens=None,
            completion_tokens=None,
            total_cost_usd=None,
            raw_output={
                "title": brief.title,
                "summary": brief.summary,
                "key_points": brief.key_points,
                "confidence": brief.confidence,
                "citations": [_citation_to_dict(citation) for citation in brief.citations],
            },
        )

    async def _run_workflow(
        self,
        session: AsyncSession,
        test_case: EvaluationTestCase,
        config: RunEvaluationConfig,
    ) -> EvaluationExecutionContext:
        started = time.perf_counter()
        topic = str(test_case.input_payload.get("topic", test_case.query))
        company_id = test_case.input_payload.get("company_id", config.company_id)
        max_retries = int(test_case.input_payload.get("max_retries", config.max_retries))
        workflow = await self._workflow_service.run_workflow(
            session,
            user_request=test_case.query,
            topic=topic,
            company_id=company_id,
            max_retries=max_retries,
        )
        latency_ms = (time.perf_counter() - started) * 1000
        citations = [
            Citation(
                document_id=str(item.get("document_id", "")),
                title=item.get("title"),
                chunk_id=str(item.get("chunk_id", "")),
                page_number=item.get("page_number"),
                score=float(item.get("score", 0.0)),
                snippet=str(item.get("snippet", "")),
            )
            for item in workflow.state.get("citations", [])
        ]
        answer = ""
        if workflow.final_output:
            answer = str(workflow.final_output.get("summary") or workflow.final_output.get("answer") or "")
        return EvaluationExecutionContext(
            answer=answer,
            citations=citations,
            confidence=workflow.confidence,
            retrieved_chunk_ids=[citation.chunk_id for citation in citations],
            latency_ms=latency_ms,
            llm_provider=None,
            llm_model=None,
            prompt_tokens=None,
            completion_tokens=None,
            total_cost_usd=None,
            raw_output={
                "workflow_id": workflow.workflow_id,
                "status": workflow.status.value,
                "confidence": workflow.confidence,
                "final_output": workflow.final_output,
                "errors": workflow.errors,
            },
        )

    async def _score_test_case(
        self,
        *,
        test_case: EvaluationTestCase,
        execution: EvaluationExecutionContext,
        config: RunEvaluationConfig,
        registry: ScorerRegistry,
        enabled_scorers: list[str],
    ) -> list[ScorerResult]:
        context_text = " ".join(citation.snippet for citation in execution.citations)
        scorer_context = ScorerContext(
            test_case=test_case,
            execution=execution,
            config=config,
            context_text=context_text,
        )
        results: list[ScorerResult] = []
        for scorer in registry.resolve(enabled_scorers):
            results.append(await scorer.score(scorer_context))
        return results

    async def _mark_run_started(self, run: EvaluationRun) -> EvaluationRun:
        from datetime import datetime, timezone

        return EvaluationRun(
            run_id=run.run_id,
            dataset_id=run.dataset_id,
            status=EvaluationRunStatus.RUNNING,
            target_type=run.target_type,
            config=run.config,
            baseline_run_id=run.baseline_run_id,
            llm_provider=run.llm_provider,
            llm_model=run.llm_model,
            summary=run.summary,
            error_message=run.error_message,
            created_at=run.created_at,
            updated_at=run.updated_at,
            started_at=datetime.now(timezone.utc),
            completed_at=None,
        )

    async def _mark_run_completed(
        self,
        run: EvaluationRun,
        *,
        summary: dict[str, Any],
        llm_provider: str | None,
        llm_model: str | None,
    ) -> EvaluationRun:
        from datetime import datetime, timezone

        return EvaluationRun(
            run_id=run.run_id,
            dataset_id=run.dataset_id,
            status=EvaluationRunStatus.COMPLETED,
            target_type=run.target_type,
            config=run.config,
            baseline_run_id=run.baseline_run_id,
            llm_provider=llm_provider,
            llm_model=llm_model,
            summary=summary,
            error_message=run.error_message,
            created_at=run.created_at,
            updated_at=run.updated_at,
            started_at=run.started_at,
            completed_at=datetime.now(timezone.utc),
        )


def _build_filters(test_case: EvaluationTestCase, config: RunEvaluationConfig) -> RetrievalFilters:
    payload = test_case.input_payload
    return RetrievalFilters(
        document_ids=payload.get("document_ids"),
        company=payload.get("company"),
        document_type=payload.get("document_type"),
        source=payload.get("source"),
        date_from=payload.get("date_from"),
        date_to=payload.get("date_to"),
        tags=payload.get("tags"),
    )


def _average_score(chunks) -> float | None:
    if not chunks:
        return None
    return round(sum(chunk.score for chunk in chunks) / len(chunks), 4)


def _citation_to_dict(citation: Citation) -> dict[str, Any]:
    return {
        "document_id": citation.document_id,
        "title": citation.title,
        "chunk_id": citation.chunk_id,
        "page_number": citation.page_number,
        "score": citation.score,
        "snippet": citation.snippet,
    }


def _config_to_dict(config: RunEvaluationConfig) -> dict[str, Any]:
    return {
        "mode": config.mode,
        "top_k": config.top_k,
        "pass_threshold": config.pass_threshold,
        "enabled_scorers": config.enabled_scorers,
        "latency_threshold_ms": config.latency_threshold_ms,
        "cost_threshold_usd": config.cost_threshold_usd,
        "company_id": config.company_id,
        "max_retries": config.max_retries,
    }


def _token_usage_dict(execution: EvaluationExecutionContext) -> dict[str, Any]:
    return {
        "prompt_tokens": execution.prompt_tokens,
        "completion_tokens": execution.completion_tokens,
        "total_cost_usd": execution.total_cost_usd,
    }


def _weighted_overall_score(scorer_results: list[ScorerResult], test_case: EvaluationTestCase) -> float:
    if not scorer_results:
        return 0.0
    weights = test_case.rubric.scorer_weights
    if weights:
        total_weight = 0.0
        weighted_sum = 0.0
        for result in scorer_results:
            weight = float(weights.get(result.scorer, 1.0))
            weighted_sum += result.score * weight
            total_weight += weight
        return round(weighted_sum / max(total_weight, 1.0), 4)

    return round(sum(result.score for result in scorer_results) / len(scorer_results), 4)


def _derive_failure_modes(scorer_results: list[ScorerResult]) -> list[FailureMode]:
    modes: list[FailureMode] = []
    for result in scorer_results:
        if result.passed:
            continue
        mode = FAILURE_MODE_BY_SCORER.get(result.scorer)
        if mode is not None and mode not in modes:
            modes.append(mode)
    return modes


def _build_run_summary(results: list[EvaluationResult]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for result in results if result.passed)
    average_score = round(sum(result.overall_score for result in results) / total, 4) if total else 0.0
    failure_mode_summary: dict[str, int] = {}
    for result in results:
        for mode in result.failure_modes:
            failure_mode_summary[mode.value] = failure_mode_summary.get(mode.value, 0) + 1
    return {
        "total_test_cases": total,
        "passed_test_cases": passed,
        "failed_test_cases": total - passed,
        "average_score": average_score,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "failure_mode_summary": failure_mode_summary,
    }


def _resolve_provider(results: list[EvaluationResult]) -> str | None:
    for result in results:
        provider = result.actual_output.get("llm_provider")
        if provider:
            return str(provider)
    return None


def _resolve_model(results: list[EvaluationResult]) -> str | None:
    for result in results:
        model = result.actual_output.get("llm_model")
        if model:
            return str(model)
    return None

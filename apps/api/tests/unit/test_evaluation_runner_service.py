from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from apps.api.app.domain.evaluation import (
    BenchmarkDataset,
    EvaluationResult,
    EvaluationRun,
    EvaluationRunStatus,
    EvaluationTargetType,
    EvaluationTestCase,
    ExpectedAnswer,
    FailureMode,
    RunEvaluationConfig,
    ScoringRubric,
)
from apps.api.app.domain.retrieval import Citation, RetrievalResult, RetrievedChunk
from apps.api.app.domain.workflows import WorkflowRun, WorkflowStatus
from apps.api.app.evaluation.judge import HeuristicEvaluationJudge
from apps.api.app.evaluation.scorers import build_default_scorer_registry
from apps.api.app.services.evaluation_runner_service import EvaluationRunnerService


NOW = datetime.now(timezone.utc)


class _FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class _FakeEvaluationRepository:
    def __init__(self) -> None:
        self.datasets: dict[str, BenchmarkDataset] = {}
        self.test_cases: dict[str, list[EvaluationTestCase]] = {}
        self.runs: dict[str, EvaluationRun] = {}
        self.results: dict[str, list[EvaluationResult]] = {}

    async def get_dataset(self, session, dataset_id):
        return self.datasets.get(dataset_id)

    async def list_test_cases(self, session, *, dataset_id):
        return self.test_cases.get(dataset_id, [])

    async def create_run(self, session, *, dataset_id, target_type, config, baseline_run_id=None):
        run = EvaluationRun(
            run_id=str(uuid4()),
            dataset_id=dataset_id,
            status=EvaluationRunStatus.PENDING,
            target_type=target_type,
            config=config,
            baseline_run_id=baseline_run_id,
            llm_provider=None,
            llm_model=None,
            summary={},
            error_message=None,
            created_at=NOW,
            updated_at=NOW,
            started_at=None,
            completed_at=None,
        )
        self.runs[run.run_id] = run
        return run

    async def save_run(self, session, run):
        self.runs[run.run_id] = run
        return run

    async def save_result(self, session, result):
        self.results.setdefault(result.run_id, []).append(result)
        return result


class _FakeRetrievalService:
    async def retrieve(self, session, *, query, mode, filters, top_k):
        return RetrievalResult(
            mode=mode,
            query=query,
            chunks=[
                RetrievedChunk(
                    chunk_id="chunk-1",
                    document_id="doc-1",
                    document_title="Annual Report",
                    text="Revenue increased steadily.",
                    score=0.9,
                )
            ],
            citations=[
                Citation(
                    document_id="doc-1",
                    title="Annual Report",
                    chunk_id="chunk-1",
                    page_number=1,
                    score=0.9,
                    snippet="Revenue increased steadily.",
                )
            ],
            total_candidates=1,
        )


class _FakeQuestionAnsweringService:
    async def answer(self, session, *, question, mode, filters, top_k):
        from apps.api.app.domain.retrieval import AssembledContext, QuestionAnswerResult

        retrieval = await _FakeRetrievalService().retrieve(
            session,
            query=question,
            mode=mode,
            filters=filters,
            top_k=top_k,
        )
        return QuestionAnswerResult(
            answer="Revenue increased steadily.",
            citations=retrieval.citations,
            confidence=0.9,
            retrieval=retrieval,
            context=AssembledContext(
                text="Revenue increased steadily.",
                citations=retrieval.citations,
                chunk_count=1,
                truncated=False,
            ),
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            finish_reason="stop",
        )


class _FakeExecutiveBriefService:
    async def generate_executive_brief(self, session, *, topic, company_id=None, mode="hybrid", top_k=6):
        from apps.api.app.domain.bi import ExecutiveBrief

        return ExecutiveBrief(
            title=f"Brief: {topic}",
            summary="Revenue increased steadily.",
            key_points=["Revenue increased steadily."],
            citations=[
                Citation(
                    document_id="doc-1",
                    title="Annual Report",
                    chunk_id="chunk-1",
                    page_number=1,
                    score=0.9,
                    snippet="Revenue increased steadily.",
                )
            ],
            confidence=0.9,
            human_review_recommended=False,
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            company_id=company_id,
            company_name="Acme",
            topic=topic,
        )


class _FakeWorkflowService:
    async def run_workflow(self, session, *, user_request, topic, company_id=None, company_ids=None, max_retries=2):
        return WorkflowRun(
            workflow_id="wf-1",
            status=WorkflowStatus.COMPLETED,
            user_request=user_request,
            company_id=company_id,
            company_ids=company_ids or [],
            topic=topic,
            plan=["document_discovery", "executive_brief"],
            completed_steps=["planner", "executive_brief"],
            failed_steps=[],
            state={
                "citations": [
                    {
                        "document_id": "doc-1",
                        "title": "Annual Report",
                        "chunk_id": "chunk-1",
                        "page_number": 1,
                        "score": 0.9,
                        "snippet": "Revenue increased steadily.",
                    }
                ]
            },
            trace=[],
            confidence=0.9,
            human_review_required=False,
            retry_count=0,
            max_retries=max_retries,
            final_output={"summary": "Revenue increased steadily."},
            errors=[],
            created_at=NOW,
            updated_at=NOW,
            started_at=NOW,
            completed_at=NOW,
        )


def _build_service(repository: _FakeEvaluationRepository) -> EvaluationRunnerService:
    return EvaluationRunnerService(
        evaluation_repository=repository,
        retrieval_service=_FakeRetrievalService(),
        question_answering_service=_FakeQuestionAnsweringService(),
        executive_brief_service=_FakeExecutiveBriefService(),
        workflow_service=_FakeWorkflowService(),
        scorer_registry=build_default_scorer_registry(HeuristicEvaluationJudge()),
    )


def _seed_dataset(
    repository: _FakeEvaluationRepository,
    *,
    dataset_id: str,
    target_type: EvaluationTargetType,
    test_cases: list[EvaluationTestCase] | None = None,
) -> str:
    repository.datasets[dataset_id] = BenchmarkDataset(
        dataset_id=dataset_id,
        name="Benchmark",
        description="Test dataset",
        target_type=target_type,
        version="1.0",
        metadata={},
        created_at=NOW,
        updated_at=NOW,
    )
    if test_cases is None:
        test_cases = [
            EvaluationTestCase(
                test_case_id="tc-1",
                dataset_id=dataset_id,
                name="Revenue case",
                query="What happened to revenue?",
                input_payload={},
                expected_answer=ExpectedAnswer(
                    text="Revenue increased steadily.",
                    required_citations=["chunk-1"],
                    required_keywords=["revenue"],
                ),
                source_documents=[],
                rubric=ScoringRubric(
                    pass_threshold=0.5,
                    enabled_scorers=["answer_accuracy", "citation_correctness", "latency"],
                ),
                tags=[],
                created_at=NOW,
                updated_at=NOW,
            )
        ]
    repository.test_cases[dataset_id] = test_cases
    return dataset_id


def test_runner_evaluates_grounded_qa_dataset() -> None:
    repository = _FakeEvaluationRepository()
    dataset_id = _seed_dataset(repository, dataset_id="dataset-1", target_type=EvaluationTargetType.GROUNDED_QA)
    service = _build_service(repository)

    run = asyncio.run(
        service.run_evaluation(
            _FakeSession(),
            dataset_id=dataset_id,
            config=RunEvaluationConfig(pass_threshold=0.5),
        )
    )

    assert run.status == EvaluationRunStatus.COMPLETED
    assert run.summary["total_test_cases"] == 1
    assert run.summary["passed_test_cases"] == 1
    assert repository.results[run.run_id][0].passed is True


def test_runner_handles_empty_dataset() -> None:
    repository = _FakeEvaluationRepository()
    dataset_id = _seed_dataset(repository, dataset_id="dataset-empty", target_type=EvaluationTargetType.RETRIEVAL, test_cases=[])
    service = _build_service(repository)

    run = asyncio.run(service.run_evaluation(_FakeSession(), dataset_id=dataset_id))

    assert run.status == EvaluationRunStatus.COMPLETED
    assert run.summary["total_test_cases"] == 0
    assert run.summary["average_score"] == 0.0


def test_runner_marks_service_errors_as_failed_results() -> None:
    repository = _FakeEvaluationRepository()
    dataset_id = _seed_dataset(repository, dataset_id="dataset-1", target_type=EvaluationTargetType.GROUNDED_QA)

    class _FailingQAService:
        async def answer(self, session, *, question, mode, filters, top_k):
            raise RuntimeError("LLM unavailable")

    service = EvaluationRunnerService(
        evaluation_repository=repository,
        retrieval_service=_FakeRetrievalService(),
        question_answering_service=_FailingQAService(),
        executive_brief_service=_FakeExecutiveBriefService(),
        workflow_service=_FakeWorkflowService(),
        scorer_registry=build_default_scorer_registry(HeuristicEvaluationJudge()),
    )

    run = asyncio.run(service.run_evaluation(_FakeSession(), dataset_id=dataset_id))
    result = repository.results[run.run_id][0]

    assert result.passed is False
    assert FailureMode.SERVICE_ERROR in result.failure_modes
    assert result.error_message == "LLM unavailable"


def test_runner_supports_retrieval_and_workflow_targets() -> None:
    repository = _FakeEvaluationRepository()
    retrieval_dataset = _seed_dataset(repository, dataset_id="dataset-retrieval", target_type=EvaluationTargetType.RETRIEVAL)
    workflow_dataset = _seed_dataset(repository, dataset_id="dataset-workflow", target_type=EvaluationTargetType.WORKFLOW)
    service = _build_service(repository)

    retrieval_run = asyncio.run(service.run_evaluation(_FakeSession(), dataset_id=retrieval_dataset))
    workflow_run = asyncio.run(service.run_evaluation(_FakeSession(), dataset_id=workflow_dataset))

    assert retrieval_run.target_type == EvaluationTargetType.RETRIEVAL
    assert workflow_run.target_type == EvaluationTargetType.WORKFLOW
    assert repository.results[retrieval_run.run_id][0].passed is True
    assert repository.results[workflow_run.run_id][0].passed is True

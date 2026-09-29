from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from apps.api.app.domain.evaluation import (
    BenchmarkDataset,
    EvaluationResult,
    EvaluationRun,
    EvaluationRunStatus,
    EvaluationTargetType,
    EvaluationTestCase,
    ExpectedAnswer,
    RunEvaluationConfig,
    ScoringRubric,
)
from apps.api.app.domain.retrieval import Citation, RetrievalResult, RetrievedChunk
from apps.api.app.domain.workflows import WorkflowRun, WorkflowStatus
from apps.api.app.evaluation.judge import HeuristicEvaluationJudge
from apps.api.app.evaluation.scorers import build_default_scorer_registry
from apps.api.app.services.evaluation_dataset_service import EvaluationDatasetService
from apps.api.app.services.evaluation_runner_service import EvaluationRunnerService


NOW = datetime.now(timezone.utc)


@dataclass
class _EvaluationStore:
    datasets: dict[str, BenchmarkDataset] = field(default_factory=dict)
    test_cases: dict[str, list[EvaluationTestCase]] = field(default_factory=dict)
    runs: dict[str, EvaluationRun] = field(default_factory=dict)
    results: dict[str, list[EvaluationResult]] = field(default_factory=dict)


class _EvaluationSession:
    def __init__(self, store: _EvaluationStore) -> None:
        self.store = store
        self.pending = _EvaluationStore()
        self.committed = False
        self.rolled_back = False

    async def commit(self) -> None:
        self.store.datasets.update(self.pending.datasets)
        for dataset_id, cases in self.pending.test_cases.items():
            self.store.test_cases.setdefault(dataset_id, []).extend(cases)
        self.store.runs.update(self.pending.runs)
        for run_id, results in self.pending.results.items():
            self.store.results.setdefault(run_id, []).extend(results)
        self.pending = _EvaluationStore()
        self.committed = True

    async def rollback(self) -> None:
        self.pending = _EvaluationStore()
        self.rolled_back = True


class _StoreBackedEvaluationRepository:
    def _datasets(self, session: _EvaluationSession) -> dict[str, BenchmarkDataset]:
        merged = dict(session.store.datasets)
        merged.update(session.pending.datasets)
        return merged

    def _test_cases(self, session: _EvaluationSession, dataset_id: str) -> list[EvaluationTestCase]:
        return list(session.store.test_cases.get(dataset_id, [])) + list(
            session.pending.test_cases.get(dataset_id, [])
        )

    async def create_dataset(
        self,
        session: _EvaluationSession,
        *,
        name: str,
        description: str,
        target_type: EvaluationTargetType,
        version: str = "1.0",
        metadata: dict | None = None,
    ) -> BenchmarkDataset:
        dataset = BenchmarkDataset(
            dataset_id=str(uuid4()),
            name=name,
            description=description,
            target_type=target_type,
            version=version,
            metadata=metadata or {},
            created_at=NOW,
            updated_at=NOW,
        )
        session.pending.datasets[dataset.dataset_id] = dataset
        session.pending.test_cases.setdefault(dataset.dataset_id, [])
        return dataset

    async def list_datasets(self, session: _EvaluationSession) -> list[BenchmarkDataset]:
        return list(self._datasets(session).values())

    async def get_dataset(self, session: _EvaluationSession, dataset_id: str) -> BenchmarkDataset | None:
        return self._datasets(session).get(dataset_id)

    async def create_test_case(
        self,
        session: _EvaluationSession,
        *,
        dataset_id: str,
        name: str,
        query: str,
        expected_answer: ExpectedAnswer,
        source_documents=None,
        rubric=None,
        input_payload=None,
        tags=None,
    ) -> EvaluationTestCase:
        test_case = EvaluationTestCase(
            test_case_id=str(uuid4()),
            dataset_id=dataset_id,
            name=name,
            query=query,
            input_payload=input_payload or {},
            expected_answer=expected_answer,
            source_documents=source_documents or [],
            rubric=rubric or ScoringRubric(),
            tags=tags or [],
            created_at=NOW,
            updated_at=NOW,
        )
        session.pending.test_cases.setdefault(dataset_id, []).append(test_case)
        return test_case

    async def list_test_cases(self, session: _EvaluationSession, *, dataset_id: str) -> list[EvaluationTestCase]:
        return self._test_cases(session, dataset_id)

    async def create_run(
        self,
        session: _EvaluationSession,
        *,
        dataset_id: str,
        target_type: EvaluationTargetType,
        config: dict,
        baseline_run_id: str | None = None,
    ) -> EvaluationRun:
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
        session.pending.runs[run.run_id] = run
        return run

    async def save_run(self, session: _EvaluationSession, run: EvaluationRun) -> EvaluationRun:
        session.pending.runs[run.run_id] = run
        return run

    async def save_result(self, session: _EvaluationSession, result: EvaluationResult) -> EvaluationResult:
        session.pending.results.setdefault(result.run_id, []).append(result)
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
            citations=[],
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
            plan=["planner"],
            completed_steps=["planner"],
            failed_steps=[],
            state={"citations": []},
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


def _new_session(store: _EvaluationStore | None = None) -> _EvaluationSession:
    return _EvaluationSession(store or _EvaluationStore())


def test_create_dataset_commits_and_persists_across_sessions() -> None:
    store = _EvaluationStore()
    repository = _StoreBackedEvaluationRepository()
    service = EvaluationDatasetService(evaluation_repository=repository)
    write_session = _new_session(store)

    created = asyncio.run(
        service.create_dataset(
            write_session,
            name="QA Benchmark",
            description="Grounded Q&A cases",
            target_type=EvaluationTargetType.GROUNDED_QA,
        )
    )

    assert write_session.committed is True
    read_session = _new_session(store)
    persisted = asyncio.run(service.get_dataset(read_session, dataset_id=created.dataset_id))
    assert persisted.name == "QA Benchmark"


def test_create_test_case_commits_and_persists_across_sessions() -> None:
    store = _EvaluationStore()
    repository = _StoreBackedEvaluationRepository()
    service = EvaluationDatasetService(evaluation_repository=repository)
    write_session = _new_session(store)

    dataset = asyncio.run(
        service.create_dataset(
            write_session,
            name="QA Benchmark",
            description="",
            target_type=EvaluationTargetType.GROUNDED_QA,
        )
    )
    asyncio.run(
        service.create_test_case(
            _new_session(store),
            dataset_id=dataset.dataset_id,
            name="Revenue case",
            query="What happened to revenue?",
            expected_answer=ExpectedAnswer(text="Revenue increased steadily."),
        )
    )

    read_session = _new_session(store)
    test_cases = asyncio.run(service.list_test_cases(read_session, dataset_id=dataset.dataset_id))
    assert len(test_cases) == 1
    assert test_cases[0].query == "What happened to revenue?"


def test_run_evaluation_commits_run_and_results_across_sessions() -> None:
    store = _EvaluationStore()
    repository = _StoreBackedEvaluationRepository()
    dataset_service = EvaluationDatasetService(evaluation_repository=repository)
    runner_service = EvaluationRunnerService(
        evaluation_repository=repository,
        retrieval_service=_FakeRetrievalService(),
        question_answering_service=_FakeQuestionAnsweringService(),
        executive_brief_service=_FakeExecutiveBriefService(),
        workflow_service=_FakeWorkflowService(),
        scorer_registry=build_default_scorer_registry(HeuristicEvaluationJudge()),
    )
    write_session = _new_session(store)

    dataset = asyncio.run(
        dataset_service.create_dataset(
            write_session,
            name="QA Benchmark",
            description="",
            target_type=EvaluationTargetType.GROUNDED_QA,
        )
    )
    asyncio.run(
        dataset_service.create_test_case(
            _new_session(store),
            dataset_id=dataset.dataset_id,
            name="Revenue case",
            query="What happened to revenue?",
            expected_answer=ExpectedAnswer(
                text="Revenue increased steadily.",
                required_citations=["chunk-1"],
                required_keywords=["revenue"],
            ),
            rubric=ScoringRubric(
                pass_threshold=0.5,
                enabled_scorers=["answer_accuracy", "citation_correctness", "latency"],
            ),
        )
    )

    run = asyncio.run(
        runner_service.run_evaluation(
            _new_session(store),
            dataset_id=dataset.dataset_id,
            config=RunEvaluationConfig(pass_threshold=0.5),
        )
    )

    assert run.status == EvaluationRunStatus.COMPLETED
    read_session = _new_session(store)
    assert read_session.store.runs[run.run_id].status == EvaluationRunStatus.COMPLETED
    assert len(read_session.store.results[run.run_id]) == 1
    assert read_session.store.results[run.run_id][0].passed is True


def test_run_evaluation_rolls_back_on_failure() -> None:
    store = _EvaluationStore()
    repository = _StoreBackedEvaluationRepository()
    dataset_service = EvaluationDatasetService(evaluation_repository=repository)

    class _FailingRepository(_StoreBackedEvaluationRepository):
        async def save_result(self, session, result):
            raise RuntimeError("database write failed")

    runner_service = EvaluationRunnerService(
        evaluation_repository=_FailingRepository(),
        retrieval_service=_FakeRetrievalService(),
        question_answering_service=_FakeQuestionAnsweringService(),
        executive_brief_service=_FakeExecutiveBriefService(),
        workflow_service=_FakeWorkflowService(),
        scorer_registry=build_default_scorer_registry(HeuristicEvaluationJudge()),
    )
    write_session = _new_session(store)

    dataset = asyncio.run(
        dataset_service.create_dataset(
            write_session,
            name="QA Benchmark",
            description="",
            target_type=EvaluationTargetType.GROUNDED_QA,
        )
    )
    asyncio.run(
        dataset_service.create_test_case(
            _new_session(store),
            dataset_id=dataset.dataset_id,
            name="Revenue case",
            query="What happened to revenue?",
            expected_answer=ExpectedAnswer(text="Revenue increased steadily."),
        )
    )

    session = _new_session(store)
    with pytest.raises(RuntimeError, match="database write failed"):
        asyncio.run(
            runner_service.run_evaluation(
                session,
                dataset_id=dataset.dataset_id,
            )
        )

    assert session.rolled_back is True
    read_session = _new_session(store)
    assert read_session.store.runs == {}
    assert read_session.store.results == {}

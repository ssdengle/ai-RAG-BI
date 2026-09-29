from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from apps.api.app.domain.evaluation import (
    EvaluationTargetType,
    ExpectedAnswer,
    ScoringRubric,
    SourceDocument,
)
from apps.api.app.repositories.evaluation_repository import EvaluationRepository
from apps.api.app.repositories.models import BenchmarkDatasetModel, EvaluationTestCaseModel


class _FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.flushed = False
        self.refreshed = []

    def add(self, instance) -> None:
        self.added.append(instance)

    async def flush(self) -> None:
        self.flushed = True

    async def refresh(self, instance) -> None:
        self.refreshed.append(instance)
        now = datetime.now(timezone.utc)
        if getattr(instance, "created_at", None) is None:
            instance.created_at = now
        if getattr(instance, "updated_at", None) is None:
            instance.updated_at = now


def test_create_dataset_persists_benchmark_dataset() -> None:
    session = _FakeSession()
    repository = EvaluationRepository()

    dataset = asyncio.run(
        repository.create_dataset(
            session,
            name="QA Benchmark",
            description="Grounded Q&A cases",
            target_type=EvaluationTargetType.GROUNDED_QA,
        )
    )

    assert len(session.added) == 1
    assert isinstance(session.added[0], BenchmarkDatasetModel)
    assert dataset.name == "QA Benchmark"
    assert dataset.target_type == EvaluationTargetType.GROUNDED_QA


def test_create_test_case_persists_expected_answer_and_rubric() -> None:
    session = _FakeSession()
    repository = EvaluationRepository()

    test_case = asyncio.run(
        repository.create_test_case(
            session,
            dataset_id="dataset-1",
            name="Revenue question",
            query="What happened to revenue?",
            expected_answer=ExpectedAnswer(
                text="Revenue increased steadily.",
                required_citations=["chunk-1"],
                required_keywords=["revenue"],
                min_confidence=0.7,
            ),
            source_documents=[SourceDocument(document_id="doc-1", title="Annual Report", chunk_ids=["chunk-1"])],
            rubric=ScoringRubric(pass_threshold=0.8, enabled_scorers=["answer_accuracy", "latency"]),
            tags=["finance"],
        )
    )

    assert len(session.added) == 1
    assert isinstance(session.added[0], EvaluationTestCaseModel)
    assert test_case.expected_answer.text == "Revenue increased steadily."
    assert test_case.rubric.pass_threshold == 0.8
    assert test_case.tags == ["finance"]

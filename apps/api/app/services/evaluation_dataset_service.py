from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.core.errors import DomainError
from apps.api.app.domain.evaluation import (
    BenchmarkDataset,
    EvaluationTargetType,
    EvaluationTestCase,
    ExpectedAnswer,
    ScoringRubric,
    SourceDocument,
)
from apps.api.app.repositories.evaluation_repository import EvaluationRepository


class EvaluationDatasetService:
    def __init__(self, *, evaluation_repository: EvaluationRepository) -> None:
        self._evaluation_repository = evaluation_repository

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
        dataset = await self._evaluation_repository.create_dataset(
            session,
            name=name,
            description=description,
            target_type=target_type,
            version=version,
            metadata=metadata,
        )
        await session.commit()
        return dataset

    async def list_datasets(self, session: AsyncSession) -> list[BenchmarkDataset]:
        return await self._evaluation_repository.list_datasets(session)

    async def get_dataset(self, session: AsyncSession, *, dataset_id: str) -> BenchmarkDataset:
        dataset = await self._evaluation_repository.get_dataset(session, dataset_id)
        if dataset is None:
            raise DomainError(
                "Benchmark dataset was not found.",
                details=dataset_id,
                code="dataset_not_found",
                status_code=404,
            )
        return dataset

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
        dataset = await self._evaluation_repository.get_dataset(session, dataset_id)
        if dataset is None:
            raise DomainError(
                "Benchmark dataset was not found.",
                details=dataset_id,
                code="dataset_not_found",
                status_code=404,
            )
        test_case = await self._evaluation_repository.create_test_case(
            session,
            dataset_id=dataset_id,
            name=name,
            query=query,
            expected_answer=expected_answer,
            source_documents=source_documents,
            rubric=rubric,
            input_payload=input_payload,
            tags=tags,
        )
        await session.commit()
        return test_case

    async def list_test_cases(self, session: AsyncSession, *, dataset_id: str) -> list[EvaluationTestCase]:
        await self.get_dataset(session, dataset_id=dataset_id)
        return await self._evaluation_repository.list_test_cases(session, dataset_id=dataset_id)

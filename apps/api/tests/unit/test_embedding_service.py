from __future__ import annotations

import asyncio

from apps.api.app.core.errors import ExternalServiceError
from apps.api.app.rag.embeddings import EmbeddingBatchResult, EmbeddingBatchUsage
from apps.api.app.services.embedding_service import EmbeddingGenerationService
from apps.api.tests.conftest import build_persisted_chunk


class _FakeProvider:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed_texts(self, texts: list[str]) -> EmbeddingBatchResult:
        self.calls.append(texts)
        vectors = [[float(index + 1), float(index + 2)] for index, _ in enumerate(texts)]
        return EmbeddingBatchResult(
            vectors=vectors,
            provider="openai",
            model="text-embedding-3-small",
            dimensions=2,
            usage=EmbeddingBatchUsage(prompt_tokens=12, total_cost_usd=0.00024),
        )


class _FlakyProvider:
    def __init__(self) -> None:
        self.attempts = 0

    async def embed_texts(self, texts: list[str]) -> EmbeddingBatchResult:
        self.attempts += 1
        if self.attempts < 2:
            raise ExternalServiceError("temporary failure", code="temporary_failure")
        return EmbeddingBatchResult(
            vectors=[[0.1, 0.2] for _ in texts],
            provider="openai",
            model="text-embedding-3-small",
            dimensions=2,
            usage=EmbeddingBatchUsage(prompt_tokens=4, total_cost_usd=0.00008),
        )


def test_embedding_service_batches_chunks_and_allocates_usage() -> None:
    provider = _FakeProvider()
    service = EmbeddingGenerationService(provider=provider, batch_size=2, max_retries=2)
    chunks = [
        build_persisted_chunk(chunk_id="chunk-1", index=0),
        build_persisted_chunk(chunk_id="chunk-2", index=1),
        build_persisted_chunk(chunk_id="chunk-3", index=2),
    ]

    results = asyncio.run(service.generate_for_chunks(chunks))

    assert len(provider.calls) == 2
    assert len(results) == 3
    assert all(result.provider == "openai" for result in results)
    assert sum(result.token_count or 0 for result in results) == 24


def test_embedding_service_retries_transient_provider_failures() -> None:
    provider = _FlakyProvider()
    service = EmbeddingGenerationService(provider=provider, batch_size=2, max_retries=3)

    results = asyncio.run(service.generate_for_chunks([build_persisted_chunk()]))

    assert provider.attempts == 2
    assert results[0].vector == [0.1, 0.2]

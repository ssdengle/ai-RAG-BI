from __future__ import annotations

import asyncio

import pytest

from apps.api.app.core.errors import DomainError, ExternalServiceError
from apps.api.app.domain.documents import IndexingStatus
from apps.api.app.rag.embeddings import GeneratedChunkEmbedding
from apps.api.app.services.vector_indexing_service import VectorIndexingService
from apps.api.tests.conftest import build_persisted_chunk, build_persisted_document


class _FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class _FakeRepository:
    def __init__(self, *, document_exists: bool = True) -> None:
        self.document_exists = document_exists
        self.clear_calls = 0
        self.started = False
        self.failed = False
        self.saved_embeddings = None

    async def get_document_model(self, session, document_id):
        if not self.document_exists:
            return None
        return type(
            "DocumentModelStub",
            (),
            {
                "document_id": document_id,
                "chunks": [build_persisted_chunk(chunk_id="chunk-1"), build_persisted_chunk(chunk_id="chunk-2")],
            },
        )()

    async def clear_embeddings(self, session, document_id):
        self.clear_calls += 1

    async def mark_indexing_started(self, session, document_id):
        self.started = True
        return build_persisted_document(document_id=document_id)

    async def get_chunks(self, session, document_id):
        return [build_persisted_chunk(chunk_id="chunk-1"), build_persisted_chunk(chunk_id="chunk-2")]

    async def save_chunk_embeddings(self, session, document_id, *, embeddings):
        self.saved_embeddings = embeddings
        document = build_persisted_document(document_id=document_id)
        return document.__class__(**{**document.__dict__, "indexing_status": IndexingStatus.INDEXED})

    async def mark_indexing_failed(self, session, document_id, *, error_message):
        self.failed = True
        return build_persisted_document(document_id=document_id)


class _FakeEmbeddingService:
    async def generate_for_chunks(self, chunks):
        return [
            GeneratedChunkEmbedding(
                chunk_id=chunk.chunk_id,
                vector=[0.1, 0.2],
                provider="openai",
                model="text-embedding-3-small",
                dimensions=2,
                token_count=5,
                cost_usd=0.00001,
            )
            for chunk in chunks
        ]


class _FailingEmbeddingService:
    async def generate_for_chunks(self, chunks):
        raise ExternalServiceError("provider failed", code="provider_failed")


def test_vector_indexing_service_indexes_document() -> None:
    repository = _FakeRepository()
    service = VectorIndexingService(
        document_repository=repository,
        embedding_service=_FakeEmbeddingService(),
    )
    session = _FakeSession()

    result = asyncio.run(service.index_document(session, document_id="doc-1", reindex=False))

    assert repository.started is True
    assert repository.saved_embeddings is not None
    assert session.commits >= 2
    assert result.document_id == "doc-1"


def test_vector_indexing_service_reindexes_when_requested() -> None:
    repository = _FakeRepository()
    service = VectorIndexingService(
        document_repository=repository,
        embedding_service=_FakeEmbeddingService(),
    )
    session = _FakeSession()

    asyncio.run(service.index_document(session, document_id="doc-1", reindex=True))

    assert repository.clear_calls == 1


def test_vector_indexing_service_marks_failure_when_embedding_fails() -> None:
    repository = _FakeRepository()
    service = VectorIndexingService(
        document_repository=repository,
        embedding_service=_FailingEmbeddingService(),
    )
    session = _FakeSession()

    with pytest.raises(ExternalServiceError):
        asyncio.run(service.index_document(session, document_id="doc-1", reindex=False))

    assert session.rollbacks == 1
    assert repository.failed is True


def test_vector_indexing_service_rejects_missing_document() -> None:
    repository = _FakeRepository(document_exists=False)
    service = VectorIndexingService(
        document_repository=repository,
        embedding_service=_FakeEmbeddingService(),
    )
    session = _FakeSession()

    with pytest.raises(DomainError):
        asyncio.run(service.index_document(session, document_id="missing", reindex=False))

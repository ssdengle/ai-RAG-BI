from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from apps.api.app.domain.documents import ChunkingOptions
from apps.api.app.rag.embeddings import GeneratedChunkEmbedding
from apps.api.app.rag.service import DocumentIngestionService
from apps.api.app.repositories.document_repository import DocumentRepository
from apps.api.app.repositories.models import DocumentChunkModel, DocumentModel


class _FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.deleted = []
        self.flushed = False
        self.refreshed = []

    def add(self, instance) -> None:
        self.added.append(instance)

    async def flush(self) -> None:
        self.flushed = True

    async def refresh(self, instance) -> None:
        self.refreshed.append(instance)
        if instance.created_at is None:
            instance.created_at = datetime.now(timezone.utc)
        if instance.updated_at is None:
            instance.updated_at = datetime.now(timezone.utc)

    async def delete(self, instance) -> None:
        self.deleted.append(instance)


def test_create_document_persists_document_and_chunks() -> None:
    session = _FakeSession()
    repository = DocumentRepository()
    ingestion_service = DocumentIngestionService()
    ingested_document = ingestion_service.ingest(
        filename="analysis.txt",
        content_type="text/plain",
        content=b"Revenue increased.\n\nMargins improved.",
        options=ChunkingOptions(strategy="semantic", max_chunk_size=80),
        document_id="doc-123",
    )

    persisted_document = asyncio.run(
        repository.create_document(session, ingested_document=ingested_document)
    )

    assert len(session.added) == 1
    document_model = session.added[0]
    assert isinstance(document_model, DocumentModel)
    assert document_model.document_id == "doc-123"
    assert len(document_model.chunks) == len(ingested_document.chunks)
    assert all(isinstance(chunk, DocumentChunkModel) for chunk in document_model.chunks)
    assert persisted_document.document_id == "doc-123"
    assert persisted_document.chunk_count == len(ingested_document.chunks)


def test_save_chunk_embeddings_updates_chunk_persistence_metadata() -> None:
    repository = DocumentRepository()
    session = _FakeSession()
    now = datetime.now(timezone.utc)
    document_model = DocumentModel(
        document_id="doc-123",
        filename="analysis.txt",
        extension=".txt",
        mime_type="text/plain",
        checksum_sha256="checksum",
        size_bytes=10,
        title=None,
        raw_char_count=10,
        normalized_char_count=10,
        word_count=2,
        source_format="txt",
        normalized_text="Revenue up",
        attributes={},
        chunk_count=1,
        indexing_status="pending",
        indexing_error=None,
        embedding_provider=None,
        embedding_model=None,
        embedding_dimensions=None,
        indexed_at=None,
        created_at=now,
        updated_at=now,
    )
    chunk_model = DocumentChunkModel(
        chunk_id="chunk-1",
        document_id="doc-123",
        chunk_index=0,
        text="Revenue up",
        strategy="semantic",
        start_offset=0,
        end_offset=10,
        chunk_metadata={},
        embedding_provider=None,
        embedding_model=None,
        embedding_dimensions=None,
        embedding_token_count=None,
        embedding_cost_usd=None,
        embedding_vector=None,
        embedded_at=None,
        created_at=now,
        updated_at=now,
    )
    document_model.chunks = [chunk_model]

    async def fake_require_document_model(_session, _document_id):
        return document_model

    repository._require_document_model = fake_require_document_model  # type: ignore[method-assign]

    persisted_document = asyncio.run(
        repository.save_chunk_embeddings(
            session,
            "doc-123",
            embeddings=[
                GeneratedChunkEmbedding(
                    chunk_id="chunk-1",
                    vector=[0.1, 0.2, 0.3],
                    provider="openai",
                    model="text-embedding-3-small",
                    dimensions=3,
                    token_count=12,
                    cost_usd=0.0001,
                )
            ],
        )
    )

    assert chunk_model.embedding_provider == "openai"
    assert chunk_model.embedding_model == "text-embedding-3-small"
    assert chunk_model.embedding_token_count == 12
    assert chunk_model.embedding_vector == [0.1, 0.2, 0.3]
    assert persisted_document.indexing_status.value == "indexed"

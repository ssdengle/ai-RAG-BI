from __future__ import annotations

import asyncio

import pytest

from apps.api.app.core.errors import DomainError
from apps.api.app.domain.documents import (
    ChunkExplorerFilters,
    DocumentBrowseFilters,
    DocumentBrowsePage,
    DocumentBrowseQuery,
    IndexingStatus,
    KnowledgeBaseStatistics,
)
from apps.api.app.services.knowledge_base_service import KnowledgeBaseService
from apps.api.tests.conftest import build_persisted_chunk, build_persisted_document


class _FakeDocumentRepository:
    def __init__(self) -> None:
        self.document = build_persisted_document(
            document_id="doc-1",
            attributes={
                "company": "Acme",
                "document_type": "10-K",
                "source": "edgar",
                "tags": ["finance"],
            },
        )
        self.last_browse_query = None
        self.last_chunk_filters = None

    async def browse_documents(self, session, *, query):
        self.last_browse_query = query
        return DocumentBrowsePage(
            items=[self.document],
            total=1,
            page=query.page,
            page_size=query.page_size,
        )

    async def get_document(self, session, document_id):
        if document_id == self.document.document_id:
            return self.document
        return None

    async def get_document_embedding_count(self, session, *, document_id):
        assert document_id == self.document.document_id
        return 2

    async def browse_document_chunks(self, session, *, document_id, filters):
        self.last_chunk_filters = filters
        return (
            [
                build_persisted_chunk(
                    chunk_id="chunk-1",
                    document_id=document_id,
                    index=0,
                    metadata={"page_number": 3, "tags": ["finance"]},
                    embedding_vector=[0.1, 0.2, 0.3],
                )
            ],
            1,
        )

    async def get_chunk(self, session, *, document_id, chunk_id):
        if chunk_id == "chunk-1":
            return build_persisted_chunk(chunk_id=chunk_id, document_id=document_id)
        return None

    async def get_failed_chunks(self, session, *, document_id):
        return [
            build_persisted_chunk(
                chunk_id="chunk-failed",
                document_id=document_id,
                metadata={"page_number": 5, "tags": ["finance"]},
            )
        ]

    async def get_knowledge_base_statistics(self, session):
        return KnowledgeBaseStatistics(
            total_documents=4,
            total_chunks=10,
            indexed_chunks=8,
            failed_chunks=2,
            documents_by_type={"10-K": 3, "unknown": 1},
            documents_by_company={"Acme": 2, "Globex": 2},
            average_chunks_per_document=2.5,
        )


def test_browse_documents_forwards_filters_sorting_and_pagination() -> None:
    repository = _FakeDocumentRepository()
    service = KnowledgeBaseService(document_repository=repository)
    query = DocumentBrowseQuery(
        filters=DocumentBrowseFilters(
            company="Acme",
            document_type="10-K",
            source="edgar",
            indexing_status=IndexingStatus.PENDING,
            search="finance",
            tags=["finance"],
        ),
        sort_by="title",
        sort_direction="asc",
        page=2,
        page_size=5,
    )

    result = asyncio.run(service.browse_documents(None, query=query))

    assert result.total == 1
    assert repository.last_browse_query == query


def test_get_document_detail_includes_embedding_count() -> None:
    repository = _FakeDocumentRepository()
    service = KnowledgeBaseService(document_repository=repository)

    detail = asyncio.run(service.get_document_detail(None, document_id="doc-1"))

    assert detail.document.document_id == "doc-1"
    assert detail.embedding_count == 2
    assert detail.last_indexed_at is None


def test_list_document_chunks_returns_filtered_chunk_view() -> None:
    repository = _FakeDocumentRepository()
    service = KnowledgeBaseService(document_repository=repository)
    filters = ChunkExplorerFilters(
        page_number=3,
        tags=["finance"],
        embedding_status="embedded",
    )

    result = asyncio.run(
        service.list_document_chunks(
            None,
            document_id="doc-1",
            filters=filters,
        )
    )

    assert result.total == 1
    assert result.chunks[0].chunk_id == "chunk-1"
    assert repository.last_chunk_filters == filters


def test_get_document_chunk_raises_not_found_for_unknown_chunk() -> None:
    repository = _FakeDocumentRepository()
    service = KnowledgeBaseService(document_repository=repository)

    with pytest.raises(DomainError) as exc_info:
        asyncio.run(
            service.get_document_chunk(
                None,
                document_id="doc-1",
                chunk_id="missing-chunk",
            )
        )

    assert exc_info.value.code == "document_chunk_not_found"


def test_indexing_visibility_surfaces_failed_chunks_and_retry_eligibility() -> None:
    repository = _FakeDocumentRepository()
    repository.document = build_persisted_document(
        document_id="doc-1",
        indexing_status=IndexingStatus.FAILED,
        indexing_error="embedding provider timeout",
        attributes={"company": "Acme"},
    )
    service = KnowledgeBaseService(document_repository=repository)

    visibility = asyncio.run(service.get_indexing_visibility(None, document_id="doc-1"))

    assert visibility.document.indexing_status == IndexingStatus.FAILED
    assert visibility.retry_eligible is True
    assert len(visibility.failed_chunks) == 1
    assert visibility.history_available is False


def test_knowledge_base_statistics_are_returned_from_repository() -> None:
    repository = _FakeDocumentRepository()
    service = KnowledgeBaseService(document_repository=repository)

    statistics = asyncio.run(service.get_knowledge_base_statistics(None))

    assert statistics.total_documents == 4
    assert statistics.documents_by_company["Acme"] == 2

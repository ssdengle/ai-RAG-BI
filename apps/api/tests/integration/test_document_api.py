from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.app.api.documents import (
    get_document_service,
    get_knowledge_base_service,
    get_vector_indexing_service,
)
from apps.api.app.core.database import get_db_session
from apps.api.app.domain.documents import (
    ChunkExplorerView,
    DocumentBrowsePage,
    DocumentDetailView,
    IndexingStatus,
    IndexingVisibilityView,
    KnowledgeBaseStatistics,
)
from apps.api.app.main import create_app
from apps.api.tests.conftest import (
    FakeDatabaseManager,
    FakeRedisManager,
    build_persisted_chunk,
    build_persisted_document,
    build_test_settings,
)


class _FakeDocumentService:
    async def upload_document(self, session, *, filename, content_type, content, options, attributes=None):
        document = build_persisted_document(document_id="doc-uploaded")
        return document.__class__(
            **{
                **document.__dict__,
                "filename": filename,
                "attributes": attributes or {},
            }
        )

    async def delete_document(self, session, *, document_id):
        return None


class _FakeKnowledgeBaseService:
    def __init__(self) -> None:
        self.last_browse_query = None
        self.last_chunk_filters = None

    async def browse_documents(self, session, *, query):
        self.last_browse_query = query
        return DocumentBrowsePage(
            items=[
                build_persisted_document(
                    document_id="doc-1",
                    title="Annual Report",
                    indexing_status=IndexingStatus.FAILED,
                    indexing_error="embedding timeout",
                    attributes={
                        "company": "Acme",
                        "document_type": "10-K",
                        "source": "edgar",
                        "date": "2024-03-01",
                        "tags": ["finance", "earnings"],
                    },
                )
            ],
            total=3,
            page=query.page,
            page_size=query.page_size,
        )

    async def get_document_detail(self, session, *, document_id):
        document = build_persisted_document(
            document_id=document_id,
            title="Annual Report",
            chunk_count=3,
            indexing_status=IndexingStatus.INDEXED,
            attributes={
                "company": "Acme",
                "document_type": "10-K",
                "source": "edgar",
                "date": "2024-03-01",
                "tags": ["finance"],
            },
            embedding_provider="openai",
            embedding_model="text-embedding-3-small",
            embedding_dimensions=1536,
        )
        return DocumentDetailView(
            document=document,
            embedding_count=2,
            last_indexed_at=document.indexed_at,
        )

    async def list_document_chunks(self, session, *, document_id, filters):
        self.last_chunk_filters = filters
        return ChunkExplorerView(
            document=build_persisted_document(document_id=document_id),
            chunks=[
                build_persisted_chunk(
                    chunk_id="chunk-1",
                    document_id=document_id,
                    index=0,
                    metadata={"page_number": 4, "tags": ["finance"]},
                    embedding_vector=[0.1, 0.2, 0.3],
                    embedding_provider="openai",
                    embedding_model="text-embedding-3-small",
                    embedding_dimensions=3,
                    embedding_token_count=12,
                    embedding_cost_usd=0.0001,
                )
            ],
            total=1,
            filters=filters,
        )

    async def get_document_chunk(self, session, *, document_id, chunk_id):
        return build_persisted_chunk(
            chunk_id=chunk_id,
            document_id=document_id,
            index=1,
            metadata={"page_number": 7, "tags": ["finance", "risk"]},
            embedding_vector=[0.1, 0.2, 0.3],
            embedding_provider="openai",
            embedding_model="text-embedding-3-small",
            embedding_dimensions=3,
            embedding_token_count=8,
            embedding_cost_usd=0.0001,
        )

    async def get_indexing_visibility(self, session, *, document_id):
        document = build_persisted_document(
            document_id=document_id,
            chunk_count=3,
            indexing_status=IndexingStatus.FAILED,
            indexing_error="embedding timeout",
            attributes={"company": "Acme"},
        )
        return IndexingVisibilityView(
            document=document,
            embedding_count=1,
            failed_chunks=[
                build_persisted_chunk(
                    chunk_id="chunk-failed",
                    document_id=document_id,
                    index=2,
                    metadata={"page_number": 8, "tags": ["finance"]},
                )
            ],
            retry_eligible=True,
        )

    async def get_knowledge_base_statistics(self, session):
        return KnowledgeBaseStatistics(
            total_documents=4,
            total_chunks=12,
            indexed_chunks=9,
            failed_chunks=3,
            documents_by_type={"10-K": 2, "10-Q": 1, "unknown": 1},
            documents_by_company={"Acme": 3, "Globex": 1},
            average_chunks_per_document=3.0,
        )


class _FakeIndexingService:
    async def index_document(self, session, *, document_id, reindex=False):
        document = build_persisted_document(document_id=document_id, chunk_count=2)
        return document.__class__(
            **{
                **document.__dict__,
                "indexing_status": IndexingStatus.INDEXED,
                "embedding_provider": "openai",
                "embedding_model": "text-embedding-3-small",
                "embedding_dimensions": 1536,
            }
        )


async def _override_db_session():
    yield None


def _build_test_app():
    knowledge_base_service = _FakeKnowledgeBaseService()
    app = create_app(
        settings=build_test_settings(),
        database_manager=FakeDatabaseManager(),
        redis_manager=FakeRedisManager(),
        perform_startup_checks=False,
    )
    app.state.fake_knowledge_base_service = knowledge_base_service
    app.dependency_overrides[get_db_session] = _override_db_session
    app.dependency_overrides[get_document_service] = lambda: _FakeDocumentService()
    app.dependency_overrides[get_knowledge_base_service] = lambda: knowledge_base_service
    app.dependency_overrides[get_vector_indexing_service] = lambda: _FakeIndexingService()
    return app


def test_upload_document_endpoint_returns_persisted_document() -> None:
    with TestClient(_build_test_app()) as client:
        response = client.post(
            "/v1/documents",
            files={"file": ("analysis.txt", b"Revenue improved", "text/plain")},
            data={"strategy": "semantic", "max_chunk_size": "100"},
        )

    assert response.status_code == 201
    assert response.json()["document_id"] == "doc-uploaded"
    assert response.json()["filename"] == "analysis.txt"


def test_list_documents_endpoint_supports_filters_pagination_and_sorting() -> None:
    app = _build_test_app()
    with TestClient(app) as client:
        response = client.get(
            "/v1/documents",
            params={
                "search": "acme",
                "company": "Acme",
                "document_type": "10-K",
                "source": "edgar",
                "indexing_status": "failed",
                "tags": "finance,earnings",
                "sort_by": "title",
                "sort_direction": "asc",
                "page": 2,
                "page_size": 1,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert payload["page"] == 2
    assert payload["page_size"] == 1
    assert payload["total_pages"] == 3
    assert payload["items"][0]["company"] == "Acme"
    assert payload["items"][0]["document_type"] == "10-K"

    query = app.state.fake_knowledge_base_service.last_browse_query
    assert query.filters.search == "acme"
    assert query.filters.company == "Acme"
    assert query.filters.document_type == "10-K"
    assert query.filters.source == "edgar"
    assert query.filters.indexing_status == IndexingStatus.FAILED
    assert query.filters.tags == ["finance", "earnings"]
    assert query.sort_by == "title"
    assert query.sort_direction == "asc"
    assert query.page == 2
    assert query.page_size == 1


def test_document_detail_endpoint_returns_enriched_detail() -> None:
    with TestClient(_build_test_app()) as client:
        response = client.get("/v1/documents/doc-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == "doc-1"
    assert payload["embedding_count"] == 2
    assert payload["company"] == "Acme"
    assert payload["document_type"] == "10-K"


def test_delete_document_endpoint_returns_no_content() -> None:
    with TestClient(_build_test_app()) as client:
        response = client.delete("/v1/documents/doc-1")

    assert response.status_code == 204


def test_index_document_endpoint_returns_indexing_status() -> None:
    with TestClient(_build_test_app()) as client:
        response = client.post("/v1/documents/doc-1/index")

    assert response.status_code == 200
    payload = response.json()
    assert payload["indexing_status"] == "indexed"
    assert payload["embedding_provider"] == "openai"
    assert payload["embedding_count"] == 2


def test_reindex_document_endpoint_returns_indexing_status() -> None:
    with TestClient(_build_test_app()) as client:
        response = client.post("/v1/documents/doc-1/reindex")

    assert response.status_code == 200
    payload = response.json()
    assert payload["indexing_status"] == "indexed"


def test_chunk_explorer_endpoint_returns_filtered_chunks() -> None:
    app = _build_test_app()
    with TestClient(app) as client:
        response = client.get(
            "/v1/documents/doc-1/chunks",
            params={"page_number": 4, "tags": "finance", "embedding_status": "embedded"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["chunks"][0]["page_number"] == 4
    assert payload["chunks"][0]["embedding_status"] == "embedded"
    assert payload["chunks"][0]["embedding_model"] == "text-embedding-3-small"

    filters = app.state.fake_knowledge_base_service.last_chunk_filters
    assert filters.page_number == 4
    assert filters.tags == ["finance"]
    assert filters.embedding_status == "embedded"


def test_chunk_detail_endpoint_returns_text_and_metadata() -> None:
    with TestClient(_build_test_app()) as client:
        response = client.get("/v1/documents/doc-1/chunks/chunk-42")

    assert response.status_code == 200
    payload = response.json()
    assert payload["chunk_id"] == "chunk-42"
    assert payload["page_number"] == 7
    assert payload["tags"] == ["finance", "risk"]
    assert payload["has_embedding"] is True


def test_indexing_visibility_endpoint_returns_failed_chunks_and_retry_eligibility() -> None:
    with TestClient(_build_test_app()) as client:
        response = client.get("/v1/documents/doc-1/indexing-visibility")

    assert response.status_code == 200
    payload = response.json()
    assert payload["indexing_status"] == "failed"
    assert payload["failed_chunk_count"] == 1
    assert payload["retry_eligible"] is True
    assert payload["history_available"] is False
    assert payload["failed_chunks"][0]["chunk_id"] == "chunk-failed"


def test_knowledge_base_statistics_endpoint_returns_aggregates() -> None:
    with TestClient(_build_test_app()) as client:
        response = client.get("/v1/documents/stats")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_documents"] == 4
    assert payload["total_chunks"] == 12
    assert payload["documents_by_company"]["Acme"] == 3
    assert payload["average_chunks_per_document"] == 3.0

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.core.config import get_request_settings
from apps.api.app.core.database import get_db_session
from apps.api.app.domain.documents import (
    ChunkExplorerFilters,
    ChunkingOptions,
    DocumentBrowseFilters,
    DocumentBrowseQuery,
    DocumentDetailView,
    IndexingStatus,
    IndexingVisibilityView,
    KnowledgeBaseStatistics,
    PersistedDocument,
    PersistedDocumentChunk,
)
from apps.api.app.integrations.embedding_factory import build_embedding_provider
from apps.api.app.rag.service import DocumentIngestionService
from apps.api.app.repositories.document_repository import DocumentRepository
from apps.api.app.schemas.documents import (
    DocumentChunkListResponse,
    DocumentChunkResponse,
    DocumentDetailResponse,
    DocumentIndexingHistoryEntryResponse,
    DocumentIndexingStatusResponse,
    DocumentIndexingVisibilityResponse,
    DocumentSummaryResponse,
    KnowledgeBaseStatisticsResponse,
    PaginatedDocumentListResponse,
)
from apps.api.app.services.document_service import DocumentService
from apps.api.app.services.embedding_service import EmbeddingGenerationService
from apps.api.app.services.knowledge_base_service import KnowledgeBaseService
from apps.api.app.services.vector_indexing_service import VectorIndexingService


router = APIRouter(prefix="/v1/documents", tags=["documents"])


def get_document_repository() -> DocumentRepository:
    return DocumentRepository()


def get_document_ingestion_service() -> DocumentIngestionService:
    return DocumentIngestionService()


def get_document_service(
    repository: DocumentRepository = Depends(get_document_repository),
    ingestion_service: DocumentIngestionService = Depends(get_document_ingestion_service),
) -> DocumentService:
    return DocumentService(
        document_repository=repository,
        ingestion_service=ingestion_service,
    )


def get_knowledge_base_service(
    repository: DocumentRepository = Depends(get_document_repository),
) -> KnowledgeBaseService:
    return KnowledgeBaseService(document_repository=repository)


def get_embedding_generation_service(
    request: Request,
) -> EmbeddingGenerationService:
    settings = get_request_settings(request)
    provider = build_embedding_provider(settings)
    return EmbeddingGenerationService(
        provider=provider,
        batch_size=settings.llm.embedding_batch_size,
        max_retries=settings.llm.embedding_max_retries,
    )


def get_vector_indexing_service(
    repository: DocumentRepository = Depends(get_document_repository),
    embedding_service: EmbeddingGenerationService = Depends(get_embedding_generation_service),
) -> VectorIndexingService:
    return VectorIndexingService(
        document_repository=repository,
        embedding_service=embedding_service,
    )


@router.post("", response_model=DocumentDetailResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    strategy: str = Form("recursive"),
    max_chunk_size: int = Form(800),
    overlap_size: int = Form(100),
    window_size: int = Form(120),
    step_size: int = Form(80),
    company: Optional[str] = Form(None),
    document_type: Optional[str] = Form(None),
    source: Optional[str] = Form(None),
    document_date: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    session: AsyncSession = Depends(get_db_session),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentDetailResponse:
    content = await file.read()
    attributes = {
        key: value
        for key, value in {
            "company": company,
            "document_type": document_type,
            "source": source,
            "date": document_date,
            "tags": _split_csv(tags),
        }.items()
        if value is not None
    }
    persisted_document = await document_service.upload_document(
        session,
        filename=file.filename or "uploaded-document",
        content_type=file.content_type,
        content=content,
        options=ChunkingOptions(
            strategy=strategy,  # type: ignore[arg-type]
            max_chunk_size=max_chunk_size,
            overlap_size=overlap_size,
            window_size=window_size,
            step_size=step_size,
        ),
        attributes=attributes,
    )
    return _to_document_detail_response(persisted_document, embedding_count=0)


@router.get("", response_model=PaginatedDocumentListResponse)
async def list_documents(
    search: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    document_type: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    indexing_status: Optional[IndexingStatus] = Query(None),
    tags: Optional[str] = Query(None),
    sort_by: Literal["created_at", "title", "company", "document_type", "indexing_status"] = Query(
        "created_at"
    ),
    sort_direction: Literal["asc", "desc"] = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
    knowledge_base_service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> PaginatedDocumentListResponse:
    result = await knowledge_base_service.browse_documents(
        session,
        query=DocumentBrowseQuery(
            filters=DocumentBrowseFilters(
                search=search,
                company=company,
                document_type=document_type,
                source=source,
                indexing_status=indexing_status,
                tags=_split_csv(tags),
            ),
            sort_by=sort_by,
            sort_direction=sort_direction,
            page=page,
            page_size=page_size,
        ),
    )
    total_pages = (result.total + result.page_size - 1) // result.page_size if result.total else 0
    return PaginatedDocumentListResponse(
        items=[_to_document_summary_response(document) for document in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=total_pages,
    )


@router.get("/stats", response_model=KnowledgeBaseStatisticsResponse)
async def get_knowledge_base_statistics(
    session: AsyncSession = Depends(get_db_session),
    knowledge_base_service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> KnowledgeBaseStatisticsResponse:
    statistics = await knowledge_base_service.get_knowledge_base_statistics(session)
    return _to_knowledge_base_statistics_response(statistics)


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: str,
    session: AsyncSession = Depends(get_db_session),
    knowledge_base_service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> DocumentDetailResponse:
    detail = await knowledge_base_service.get_document_detail(session, document_id=document_id)
    return _to_document_detail_view_response(detail)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_document(
    document_id: str,
    session: AsyncSession = Depends(get_db_session),
    document_service: DocumentService = Depends(get_document_service),
) -> Response:
    await document_service.delete_document(session, document_id=document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{document_id}/index", response_model=DocumentIndexingStatusResponse)
async def index_document(
    document_id: str,
    session: AsyncSession = Depends(get_db_session),
    indexing_service: VectorIndexingService = Depends(get_vector_indexing_service),
) -> DocumentIndexingStatusResponse:
    document = await indexing_service.index_document(session, document_id=document_id, reindex=False)
    return _to_indexing_status_response(
        document,
        embedding_count=_infer_embedding_count(document),
    )


@router.post("/{document_id}/reindex", response_model=DocumentIndexingStatusResponse)
async def reindex_document(
    document_id: str,
    session: AsyncSession = Depends(get_db_session),
    indexing_service: VectorIndexingService = Depends(get_vector_indexing_service),
) -> DocumentIndexingStatusResponse:
    document = await indexing_service.index_document(session, document_id=document_id, reindex=True)
    return _to_indexing_status_response(
        document,
        embedding_count=_infer_embedding_count(document),
    )


@router.get("/{document_id}/chunks", response_model=DocumentChunkListResponse)
async def view_document_chunks(
    document_id: str,
    page_number: Optional[int] = Query(None, ge=1),
    tags: Optional[str] = Query(None),
    embedding_status: Optional[Literal["embedded", "missing"]] = Query(None),
    session: AsyncSession = Depends(get_db_session),
    knowledge_base_service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> DocumentChunkListResponse:
    parsed_tags = _split_csv(tags)
    chunk_view = await knowledge_base_service.list_document_chunks(
        session,
        document_id=document_id,
        filters=ChunkExplorerFilters(
            page_number=page_number,
            tags=parsed_tags,
            embedding_status=embedding_status,
        ),
    )
    return DocumentChunkListResponse(
        document_id=document_id,
        total=chunk_view.total,
        page_number=page_number,
        tags=parsed_tags or [],
        embedding_status=embedding_status,
        chunks=[_to_chunk_response(chunk) for chunk in chunk_view.chunks],
    )


@router.get("/{document_id}/chunks/{chunk_id}", response_model=DocumentChunkResponse)
async def get_document_chunk(
    document_id: str,
    chunk_id: str,
    session: AsyncSession = Depends(get_db_session),
    knowledge_base_service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> DocumentChunkResponse:
    chunk = await knowledge_base_service.get_document_chunk(
        session,
        document_id=document_id,
        chunk_id=chunk_id,
    )
    return _to_chunk_response(chunk)


@router.get("/{document_id}/indexing-status", response_model=DocumentIndexingStatusResponse)
async def view_indexing_status(
    document_id: str,
    session: AsyncSession = Depends(get_db_session),
    knowledge_base_service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> DocumentIndexingStatusResponse:
    detail = await knowledge_base_service.get_document_detail(session, document_id=document_id)
    return _to_indexing_status_response(
        detail.document,
        embedding_count=detail.embedding_count,
    )


@router.get(
    "/{document_id}/indexing-visibility",
    response_model=DocumentIndexingVisibilityResponse,
)
async def view_indexing_visibility(
    document_id: str,
    session: AsyncSession = Depends(get_db_session),
    knowledge_base_service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> DocumentIndexingVisibilityResponse:
    visibility = await knowledge_base_service.get_indexing_visibility(
        session,
        document_id=document_id,
    )
    return _to_indexing_visibility_response(visibility)


def _to_document_summary_response(document: PersistedDocument) -> DocumentSummaryResponse:
    metadata = document.attributes or {}
    return DocumentSummaryResponse(
        document_id=document.document_id,
        filename=document.filename,
        extension=document.extension,
        mime_type=document.mime_type,
        checksum_sha256=document.checksum_sha256,
        size_bytes=document.size_bytes,
        title=document.title,
        company=_get_string_attribute(metadata, "company"),
        document_type=_get_string_attribute(metadata, "document_type"),
        source=_get_string_attribute(metadata, "source"),
        document_date=_get_string_attribute(metadata, "date"),
        tags=_get_list_attribute(metadata, "tags"),
        source_format=document.source_format,
        chunk_count=document.chunk_count,
        indexing_status=document.indexing_status.value,
        indexing_error=document.indexing_error,
        embedding_provider=document.embedding_provider,
        embedding_model=document.embedding_model,
        embedding_dimensions=document.embedding_dimensions,
        indexed_at=document.indexed_at,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def _to_document_detail_response(
    document: PersistedDocument,
    *,
    embedding_count: int,
) -> DocumentDetailResponse:
    return DocumentDetailResponse(
        **_to_document_summary_response(document).model_dump(),
        raw_char_count=document.raw_char_count,
        normalized_char_count=document.normalized_char_count,
        word_count=document.word_count,
        normalized_text=document.normalized_text,
        attributes=document.attributes,
        embedding_count=embedding_count,
        last_indexed_at=document.indexed_at,
    )


def _to_document_detail_view_response(document: DocumentDetailView) -> DocumentDetailResponse:
    return _to_document_detail_response(
        document.document,
        embedding_count=document.embedding_count,
    )


def _to_chunk_response(chunk: PersistedDocumentChunk) -> DocumentChunkResponse:
    metadata = chunk.metadata or {}
    return DocumentChunkResponse(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        index=chunk.index,
        page_number=_get_page_number(metadata),
        tags=_get_list_attribute(metadata, "tags"),
        text=chunk.text,
        strategy=chunk.strategy,
        start_offset=chunk.start_offset,
        end_offset=chunk.end_offset,
        metadata=metadata,
        embedding_status="embedded" if chunk.embedding_vector is not None else "missing",
        embedding_provider=chunk.embedding_provider,
        embedding_model=chunk.embedding_model,
        embedding_dimensions=chunk.embedding_dimensions,
        embedding_token_count=chunk.embedding_token_count,
        embedding_cost_usd=chunk.embedding_cost_usd,
        has_embedding=chunk.embedding_vector is not None,
        embedded_at=chunk.embedded_at,
        created_at=chunk.created_at,
        updated_at=chunk.updated_at,
    )


def _to_indexing_status_response(
    document: PersistedDocument,
    *,
    embedding_count: int,
) -> DocumentIndexingStatusResponse:
    return DocumentIndexingStatusResponse(
        document_id=document.document_id,
        indexing_status=document.indexing_status.value,
        indexing_error=document.indexing_error,
        embedding_provider=document.embedding_provider,
        embedding_model=document.embedding_model,
        embedding_dimensions=document.embedding_dimensions,
        indexed_at=document.indexed_at,
        last_indexed_at=document.indexed_at,
        chunk_count=document.chunk_count,
        embedding_count=embedding_count,
        updated_at=document.updated_at,
    )


def _to_indexing_visibility_response(
    visibility: IndexingVisibilityView,
) -> DocumentIndexingVisibilityResponse:
    return DocumentIndexingVisibilityResponse(
        document_id=visibility.document.document_id,
        indexing_status=visibility.document.indexing_status.value,
        indexing_error=visibility.document.indexing_error,
        chunk_count=visibility.document.chunk_count,
        embedding_count=visibility.embedding_count,
        failed_chunk_count=len(visibility.failed_chunks),
        failed_chunks=[_to_chunk_response(chunk) for chunk in visibility.failed_chunks],
        retry_eligible=visibility.retry_eligible,
        history_available=visibility.history_available,
        indexing_history=[
            DocumentIndexingHistoryEntryResponse(
                status=entry.status.value,
                timestamp=entry.timestamp,
                error=entry.error,
            )
            for entry in visibility.indexing_history
        ],
        last_indexed_at=visibility.document.indexed_at,
        updated_at=visibility.document.updated_at,
    )


def _to_knowledge_base_statistics_response(
    statistics: KnowledgeBaseStatistics,
) -> KnowledgeBaseStatisticsResponse:
    return KnowledgeBaseStatisticsResponse(
        total_documents=statistics.total_documents,
        total_chunks=statistics.total_chunks,
        indexed_chunks=statistics.indexed_chunks,
        failed_chunks=statistics.failed_chunks,
        documents_by_type=statistics.documents_by_type,
        documents_by_company=statistics.documents_by_company,
        average_chunks_per_document=statistics.average_chunks_per_document,
    )


def _split_csv(value: Optional[str]) -> Optional[list[str]]:
    if value is None:
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or None


def _get_string_attribute(metadata: dict[str, object], key: str) -> Optional[str]:
    value = metadata.get(key)
    return value if isinstance(value, str) else None


def _get_list_attribute(metadata: dict[str, object], key: str) -> list[str]:
    value = metadata.get(key)
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _get_page_number(metadata: dict[str, object]) -> Optional[int]:
    value = metadata.get("page_number")
    return value if isinstance(value, int) else None


def _infer_embedding_count(document: PersistedDocument) -> int:
    if document.indexing_status == IndexingStatus.INDEXED:
        return document.chunk_count
    return 0

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.core.errors import DomainError
from apps.api.app.core.logging import get_logger
from apps.api.app.domain.documents import (
    ChunkExplorerFilters,
    ChunkExplorerView,
    DocumentBrowsePage,
    DocumentBrowseQuery,
    DocumentDetailView,
    IndexingStatus,
    IndexingVisibilityView,
    KnowledgeBaseStatistics,
    PersistedDocument,
    PersistedDocumentChunk,
)
from apps.api.app.repositories.document_repository import DocumentRepository


class KnowledgeBaseService:
    def __init__(self, *, document_repository: DocumentRepository) -> None:
        self._document_repository = document_repository
        self._logger = get_logger("api.knowledge_base_service")

    async def browse_documents(
        self,
        session: AsyncSession,
        *,
        query: DocumentBrowseQuery,
    ) -> DocumentBrowsePage:
        return await self._document_repository.browse_documents(session, query=query)

    async def get_document_detail(
        self,
        session: AsyncSession,
        *,
        document_id: str,
    ) -> DocumentDetailView:
        document = await self._get_document_or_raise(session, document_id=document_id)
        embedding_count = await self._document_repository.get_document_embedding_count(
            session,
            document_id=document_id,
        )
        return DocumentDetailView(
            document=document,
            embedding_count=embedding_count,
            last_indexed_at=document.indexed_at,
        )

    async def list_document_chunks(
        self,
        session: AsyncSession,
        *,
        document_id: str,
        filters: ChunkExplorerFilters,
    ) -> ChunkExplorerView:
        document = await self._get_document_or_raise(session, document_id=document_id)
        chunks, total = await self._document_repository.browse_document_chunks(
            session,
            document_id=document_id,
            filters=filters,
        )
        return ChunkExplorerView(
            document=document,
            chunks=chunks,
            total=total,
            filters=filters,
        )

    async def get_document_chunk(
        self,
        session: AsyncSession,
        *,
        document_id: str,
        chunk_id: str,
    ) -> PersistedDocumentChunk:
        await self._get_document_or_raise(session, document_id=document_id)
        chunk = await self._document_repository.get_chunk(
            session,
            document_id=document_id,
            chunk_id=chunk_id,
        )
        if chunk is None:
            raise DomainError(
                "Document chunk was not found.",
                details={"document_id": document_id, "chunk_id": chunk_id},
                code="document_chunk_not_found",
                status_code=404,
            )
        return chunk

    async def get_indexing_visibility(
        self,
        session: AsyncSession,
        *,
        document_id: str,
    ) -> IndexingVisibilityView:
        document = await self._get_document_or_raise(session, document_id=document_id)
        embedding_count = await self._document_repository.get_document_embedding_count(
            session,
            document_id=document_id,
        )
        failed_chunks = []
        if document.indexing_status == IndexingStatus.FAILED:
            failed_chunks = await self._document_repository.get_failed_chunks(
                session,
                document_id=document_id,
            )

        return IndexingVisibilityView(
            document=document,
            embedding_count=embedding_count,
            failed_chunks=failed_chunks,
            indexing_history=[],
            history_available=False,
            retry_eligible=self._is_retry_eligible(document),
        )

    async def get_knowledge_base_statistics(
        self,
        session: AsyncSession,
    ) -> KnowledgeBaseStatistics:
        return await self._document_repository.get_knowledge_base_statistics(session)

    async def _get_document_or_raise(
        self,
        session: AsyncSession,
        *,
        document_id: str,
    ) -> PersistedDocument:
        document = await self._document_repository.get_document(session, document_id)
        if document is None:
            raise DomainError(
                "Document was not found.",
                details=document_id,
                code="document_not_found",
                status_code=404,
            )
        return document

    @staticmethod
    def _is_retry_eligible(document: PersistedDocument) -> bool:
        return document.indexing_status in {IndexingStatus.PENDING, IndexingStatus.FAILED}

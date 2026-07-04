from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.core.errors import DomainError
from apps.api.app.core.logging import get_logger
from apps.api.app.domain.documents import PersistedDocument
from apps.api.app.repositories.document_repository import DocumentRepository
from apps.api.app.services.embedding_service import EmbeddingGenerationService


class VectorIndexingService:
    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        embedding_service: EmbeddingGenerationService,
    ) -> None:
        self._document_repository = document_repository
        self._embedding_service = embedding_service
        self._logger = get_logger("api.vector_indexing")

    async def index_document(
        self,
        session: AsyncSession,
        *,
        document_id: str,
        reindex: bool = False,
    ) -> PersistedDocument:
        document = await self._document_repository.get_document_model(session, document_id)
        if document is None:
            raise DomainError(
                "Document was not found.",
                details=document_id,
                code="document_not_found",
                status_code=404,
            )

        if not document.chunks:
            raise DomainError(
                "Document has no chunks to index.",
                details=document_id,
                code="document_has_no_chunks",
                status_code=409,
            )

        if reindex:
            await self._document_repository.clear_embeddings(session, document_id)
            await session.commit()

        await self._document_repository.mark_indexing_started(session, document_id)
        await session.commit()

        try:
            chunks = await self._document_repository.get_chunks(session, document_id)
            generated_embeddings = await self._embedding_service.generate_for_chunks(chunks)
            persisted_document = await self._document_repository.save_chunk_embeddings(
                session,
                document_id,
                embeddings=generated_embeddings,
            )
            await session.commit()
            self._logger.info(
                "document.indexed",
                document_id=document_id,
                chunk_count=len(chunks),
                reindex=reindex,
            )
            return persisted_document
        except Exception as exc:
            await session.rollback()
            await self._document_repository.mark_indexing_failed(
                session,
                document_id,
                error_message=str(exc),
            )
            await session.commit()
            raise

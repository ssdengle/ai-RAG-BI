from __future__ import annotations

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.core.errors import DomainError
from apps.api.app.core.logging import get_logger
from apps.api.app.domain.documents import ChunkingOptions, PersistedDocument, PersistedDocumentChunk
from apps.api.app.rag.service import DocumentIngestionService
from apps.api.app.repositories.document_repository import DocumentRepository


class DocumentService:
    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        ingestion_service: DocumentIngestionService,
    ) -> None:
        self._document_repository = document_repository
        self._ingestion_service = ingestion_service
        self._logger = get_logger("api.document_service")

    async def upload_document(
        self,
        session: AsyncSession,
        *,
        filename: str,
        content_type: str | None,
        content: bytes,
        options: ChunkingOptions,
        attributes: dict[str, object] | None = None,
    ) -> PersistedDocument:
        ingested_document = self._ingestion_service.ingest(
            filename=filename,
            content_type=content_type,
            content=content,
            options=options,
            document_id=str(uuid4()),
            additional_attributes=attributes,
        )
        persisted_document = await self._document_repository.create_document(
            session,
            ingested_document=ingested_document,
        )
        await session.commit()
        self._logger.info(
            "document.uploaded",
            document_id=persisted_document.document_id,
            filename=filename,
            chunk_count=persisted_document.chunk_count,
        )
        return persisted_document

    async def list_documents(self, session: AsyncSession) -> list[PersistedDocument]:
        return await self._document_repository.list_documents(session)

    async def get_document(self, session: AsyncSession, *, document_id: str) -> PersistedDocument:
        document = await self._document_repository.get_document(session, document_id)
        if document is None:
            raise DomainError(
                "Document was not found.",
                details=document_id,
                code="document_not_found",
                status_code=404,
            )
        return document

    async def get_document_chunks(
        self,
        session: AsyncSession,
        *,
        document_id: str,
    ) -> list[PersistedDocumentChunk]:
        await self.get_document(session, document_id=document_id)
        return await self._document_repository.get_chunks(session, document_id)

    async def delete_document(self, session: AsyncSession, *, document_id: str) -> None:
        deleted = await self._document_repository.delete_document(session, document_id)
        if not deleted:
            raise DomainError(
                "Document was not found.",
                details=document_id,
                code="document_not_found",
                status_code=404,
            )
        await session.commit()
        self._logger.info("document.deleted", document_id=document_id)

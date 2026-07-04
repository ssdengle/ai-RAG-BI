from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Sequence

from sqlalchemy import Integer, Text, cast, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.api.app.domain.documents import (
    ChunkExplorerFilters,
    DocumentBrowseFilters,
    DocumentBrowsePage,
    DocumentBrowseQuery,
    DocumentChunk,
    IndexingStatus,
    IngestedDocument,
    KnowledgeBaseStatistics,
    PersistedDocument,
    PersistedDocumentChunk,
)
from apps.api.app.repositories.models import DocumentChunkModel, DocumentModel
from apps.api.app.rag.embeddings import GeneratedChunkEmbedding


class DocumentRepository:
    async def create_document(
        self,
        session: AsyncSession,
        *,
        ingested_document: IngestedDocument,
    ) -> PersistedDocument:
        document = DocumentModel(
            document_id=ingested_document.metadata.document_id,
            filename=ingested_document.metadata.filename,
            extension=ingested_document.metadata.extension,
            mime_type=ingested_document.metadata.mime_type,
            checksum_sha256=ingested_document.metadata.checksum_sha256,
            size_bytes=ingested_document.metadata.size_bytes,
            title=ingested_document.metadata.title,
            raw_char_count=ingested_document.metadata.raw_char_count,
            normalized_char_count=ingested_document.metadata.normalized_char_count,
            word_count=ingested_document.metadata.word_count,
            source_format=ingested_document.metadata.source_format,
            normalized_text=ingested_document.normalized_text,
            attributes=ingested_document.metadata.attributes,
            chunk_count=len(ingested_document.chunks),
            indexing_status=IndexingStatus.PENDING.value,
        )
        document.chunks = [self._build_chunk_model(chunk) for chunk in ingested_document.chunks]

        session.add(document)
        await session.flush()
        await session.refresh(document)
        return self._to_persisted_document(document)

    async def list_documents(self, session: AsyncSession) -> list[PersistedDocument]:
        result = await session.execute(
            select(DocumentModel).order_by(DocumentModel.created_at.desc())
        )
        documents = result.scalars().all()
        return [self._to_persisted_document(document) for document in documents]

    async def browse_documents(
        self,
        session: AsyncSession,
        *,
        query: DocumentBrowseQuery,
    ) -> DocumentBrowsePage:
        count_stmt = self._apply_document_filters(
            select(func.count()).select_from(DocumentModel),
            query.filters,
        )
        total = int((await session.execute(count_stmt)).scalar_one())

        stmt = self._apply_document_filters(select(DocumentModel), query.filters)
        stmt = self._apply_document_sort(stmt, sort_by=query.sort_by, sort_direction=query.sort_direction)
        stmt = stmt.offset((query.page - 1) * query.page_size).limit(query.page_size)

        result = await session.execute(stmt)
        documents = result.scalars().all()
        return DocumentBrowsePage(
            items=[self._to_persisted_document(document) for document in documents],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    async def get_document(self, session: AsyncSession, document_id: str) -> PersistedDocument | None:
        document = await session.get(DocumentModel, document_id)
        if document is None:
            return None
        return self._to_persisted_document(document)

    async def get_document_model(self, session: AsyncSession, document_id: str) -> DocumentModel | None:
        result = await session.execute(
            select(DocumentModel)
            .options(selectinload(DocumentModel.chunks))
            .where(DocumentModel.document_id == document_id)
        )
        return result.scalar_one_or_none()

    async def get_chunks(self, session: AsyncSession, document_id: str) -> list[PersistedDocumentChunk]:
        result = await session.execute(
            select(DocumentChunkModel)
            .where(DocumentChunkModel.document_id == document_id)
            .order_by(DocumentChunkModel.chunk_index.asc())
        )
        chunks = result.scalars().all()
        return [self._to_persisted_chunk(chunk) for chunk in chunks]

    async def browse_document_chunks(
        self,
        session: AsyncSession,
        *,
        document_id: str,
        filters: ChunkExplorerFilters,
    ) -> tuple[list[PersistedDocumentChunk], int]:
        count_stmt = self._apply_chunk_filters(
            select(func.count()).select_from(DocumentChunkModel).where(
                DocumentChunkModel.document_id == document_id
            ),
            filters,
        )
        total = int((await session.execute(count_stmt)).scalar_one())

        stmt = self._apply_chunk_filters(
            select(DocumentChunkModel).where(DocumentChunkModel.document_id == document_id),
            filters,
        ).order_by(DocumentChunkModel.chunk_index.asc())
        result = await session.execute(stmt)
        chunks = result.scalars().all()
        return [self._to_persisted_chunk(chunk) for chunk in chunks], total

    async def get_chunk(
        self,
        session: AsyncSession,
        *,
        document_id: str,
        chunk_id: str,
    ) -> PersistedDocumentChunk | None:
        result = await session.execute(
            select(DocumentChunkModel).where(
                DocumentChunkModel.document_id == document_id,
                DocumentChunkModel.chunk_id == chunk_id,
            )
        )
        chunk = result.scalar_one_or_none()
        if chunk is None:
            return None
        return self._to_persisted_chunk(chunk)

    async def get_document_embedding_count(
        self,
        session: AsyncSession,
        *,
        document_id: str,
    ) -> int:
        stmt = select(func.count()).select_from(DocumentChunkModel).where(
            DocumentChunkModel.document_id == document_id,
            DocumentChunkModel.embedding_vector.is_not(None),
        )
        return int((await session.execute(stmt)).scalar_one())

    async def get_failed_chunks(
        self,
        session: AsyncSession,
        *,
        document_id: str,
    ) -> list[PersistedDocumentChunk]:
        result = await session.execute(
            select(DocumentChunkModel)
            .where(
                DocumentChunkModel.document_id == document_id,
                DocumentChunkModel.embedding_vector.is_(None),
            )
            .order_by(DocumentChunkModel.chunk_index.asc())
        )
        chunks = result.scalars().all()
        return [self._to_persisted_chunk(chunk) for chunk in chunks]

    async def get_knowledge_base_statistics(
        self,
        session: AsyncSession,
    ) -> KnowledgeBaseStatistics:
        total_documents = int(
            (await session.execute(select(func.count()).select_from(DocumentModel))).scalar_one()
        )
        total_chunks = int(
            (await session.execute(select(func.count()).select_from(DocumentChunkModel))).scalar_one()
        )
        indexed_chunks = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(DocumentChunkModel)
                    .where(DocumentChunkModel.embedding_vector.is_not(None))
                )
            ).scalar_one()
        )
        failed_chunks = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(DocumentChunkModel)
                    .join(DocumentModel, DocumentChunkModel.document_id == DocumentModel.document_id)
                    .where(
                        DocumentModel.indexing_status == IndexingStatus.FAILED.value,
                        DocumentChunkModel.embedding_vector.is_(None),
                    )
                )
            ).scalar_one()
        )

        average_chunks_per_document = (
            float(total_chunks) / float(total_documents) if total_documents else 0.0
        )

        return KnowledgeBaseStatistics(
            total_documents=total_documents,
            total_chunks=total_chunks,
            indexed_chunks=indexed_chunks,
            failed_chunks=failed_chunks,
            documents_by_type=await self._group_documents_by_attribute(session, "document_type"),
            documents_by_company=await self._group_documents_by_attribute(session, "company"),
            average_chunks_per_document=average_chunks_per_document,
        )

    async def delete_document(self, session: AsyncSession, document_id: str) -> bool:
        document = await session.get(DocumentModel, document_id)
        if document is None:
            return False

        await session.delete(document)
        await session.flush()
        return True

    async def mark_indexing_started(self, session: AsyncSession, document_id: str) -> PersistedDocument:
        document = await self._require_document_model(session, document_id)
        document.indexing_status = IndexingStatus.INDEXING.value
        document.indexing_error = None
        await session.flush()
        return self._to_persisted_document(document)

    async def mark_indexing_failed(
        self,
        session: AsyncSession,
        document_id: str,
        *,
        error_message: str,
    ) -> PersistedDocument:
        document = await self._require_document_model(session, document_id)
        document.indexing_status = IndexingStatus.FAILED.value
        document.indexing_error = error_message
        await session.flush()
        return self._to_persisted_document(document)

    async def clear_embeddings(self, session: AsyncSession, document_id: str) -> None:
        document = await self._require_document_model(session, document_id)
        document.embedding_provider = None
        document.embedding_model = None
        document.embedding_dimensions = None
        document.indexed_at = None
        document.indexing_error = None
        document.indexing_status = IndexingStatus.PENDING.value

        for chunk in document.chunks:
            chunk.embedding_provider = None
            chunk.embedding_model = None
            chunk.embedding_dimensions = None
            chunk.embedding_token_count = None
            chunk.embedding_cost_usd = None
            chunk.embedding_vector = None
            chunk.embedded_at = None

        await session.flush()

    async def save_chunk_embeddings(
        self,
        session: AsyncSession,
        document_id: str,
        *,
        embeddings: Sequence[GeneratedChunkEmbedding],
    ) -> PersistedDocument:
        document = await self._require_document_model(session, document_id)
        chunks_by_id = {chunk.chunk_id: chunk for chunk in document.chunks}
        indexed_at = datetime.now(timezone.utc)

        for embedding in embeddings:
            chunk = chunks_by_id[embedding.chunk_id]
            chunk.embedding_provider = embedding.provider
            chunk.embedding_model = embedding.model
            chunk.embedding_dimensions = embedding.dimensions
            chunk.embedding_token_count = embedding.token_count
            chunk.embedding_cost_usd = embedding.cost_usd
            chunk.embedding_vector = embedding.vector
            chunk.embedded_at = indexed_at

        if embeddings:
            document.embedding_provider = embeddings[0].provider
            document.embedding_model = embeddings[0].model
            document.embedding_dimensions = embeddings[0].dimensions
        document.indexing_status = IndexingStatus.INDEXED.value
        document.indexing_error = None
        document.indexed_at = indexed_at

        await session.flush()
        return self._to_persisted_document(document)

    async def replace_document_chunks(
        self,
        session: AsyncSession,
        document_id: str,
        *,
        chunks: Iterable[DocumentChunk],
        chunk_count: int,
    ) -> PersistedDocument:
        document = await self._require_document_model(session, document_id)
        await session.execute(
            delete(DocumentChunkModel).where(DocumentChunkModel.document_id == document_id)
        )
        document.chunks = [self._build_chunk_model(chunk) for chunk in chunks]
        document.chunk_count = chunk_count
        document.indexing_status = IndexingStatus.PENDING.value
        document.indexed_at = None
        document.indexing_error = None
        document.embedding_provider = None
        document.embedding_model = None
        document.embedding_dimensions = None
        await session.flush()
        return self._to_persisted_document(document)

    @staticmethod
    def _apply_document_filters(stmt, filters: DocumentBrowseFilters):
        if filters.company:
            stmt = stmt.where(DocumentModel.attributes["company"].astext == filters.company)

        if filters.document_type:
            stmt = stmt.where(DocumentModel.attributes["document_type"].astext == filters.document_type)

        if filters.source:
            stmt = stmt.where(DocumentModel.attributes["source"].astext == filters.source)

        if filters.indexing_status:
            stmt = stmt.where(DocumentModel.indexing_status == filters.indexing_status.value)

        if filters.tags:
            stmt = stmt.where(DocumentModel.attributes["tags"].contains(filters.tags))

        if filters.search:
            search_term = f"%{filters.search.strip()}%"
            stmt = stmt.where(
                or_(
                    DocumentModel.filename.ilike(search_term),
                    DocumentModel.title.ilike(search_term),
                    cast(DocumentModel.attributes, Text).ilike(search_term),
                )
            )

        return stmt

    @staticmethod
    def _apply_document_sort(stmt, *, sort_by: str, sort_direction: str):
        if sort_by == "title":
            sort_expression = func.lower(func.coalesce(DocumentModel.title, DocumentModel.filename))
        elif sort_by == "company":
            sort_expression = func.lower(func.coalesce(DocumentModel.attributes["company"].astext, ""))
        elif sort_by == "document_type":
            sort_expression = func.lower(
                func.coalesce(DocumentModel.attributes["document_type"].astext, "")
            )
        elif sort_by == "indexing_status":
            sort_expression = DocumentModel.indexing_status
        else:
            sort_expression = DocumentModel.created_at

        ordered_expression = (
            sort_expression.asc() if sort_direction == "asc" else sort_expression.desc()
        )
        return stmt.order_by(ordered_expression, DocumentModel.document_id.asc())

    @staticmethod
    def _apply_chunk_filters(stmt, filters: ChunkExplorerFilters):
        if filters.page_number is not None:
            stmt = stmt.where(
                cast(DocumentChunkModel.chunk_metadata["page_number"].astext, Integer)
                == filters.page_number
            )

        if filters.tags:
            for tag in filters.tags:
                stmt = stmt.where(DocumentChunkModel.chunk_metadata["tags"].contains([tag]))

        if filters.embedding_status == "embedded":
            stmt = stmt.where(DocumentChunkModel.embedding_vector.is_not(None))
        elif filters.embedding_status == "missing":
            stmt = stmt.where(DocumentChunkModel.embedding_vector.is_(None))

        return stmt

    async def _group_documents_by_attribute(
        self,
        session: AsyncSession,
        attribute_name: str,
    ) -> dict[str, int]:
        attribute_value = func.coalesce(
            DocumentModel.attributes[attribute_name].astext,
            "unknown",
        ).label("attribute_value")
        stmt = (
            select(attribute_value, func.count(DocumentModel.document_id))
            .select_from(DocumentModel)
            .group_by(attribute_value)
            .order_by(attribute_value.asc())
        )
        rows = (await session.execute(stmt)).all()
        return {str(value): int(count) for value, count in rows}

    async def _require_document_model(self, session: AsyncSession, document_id: str) -> DocumentModel:
        document = await self.get_document_model(session, document_id)
        if document is None:
            raise KeyError(document_id)
        return document

    @staticmethod
    def _build_chunk_model(chunk: DocumentChunk) -> DocumentChunkModel:
        return DocumentChunkModel(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            chunk_index=chunk.index,
            text=chunk.text,
            strategy=chunk.strategy,
            start_offset=chunk.start_offset,
            end_offset=chunk.end_offset,
            chunk_metadata=chunk.metadata,
        )

    @staticmethod
    def _to_persisted_document(document: DocumentModel) -> PersistedDocument:
        return PersistedDocument(
            document_id=document.document_id,
            filename=document.filename,
            extension=document.extension,
            mime_type=document.mime_type,
            checksum_sha256=document.checksum_sha256,
            size_bytes=document.size_bytes,
            title=document.title,
            raw_char_count=document.raw_char_count,
            normalized_char_count=document.normalized_char_count,
            word_count=document.word_count,
            source_format=document.source_format,
            normalized_text=document.normalized_text,
            attributes=document.attributes or {},
            chunk_count=document.chunk_count,
            indexing_status=IndexingStatus(document.indexing_status),
            indexing_error=document.indexing_error,
            embedding_provider=document.embedding_provider,
            embedding_model=document.embedding_model,
            embedding_dimensions=document.embedding_dimensions,
            indexed_at=document.indexed_at,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

    @staticmethod
    def _to_persisted_chunk(chunk: DocumentChunkModel) -> PersistedDocumentChunk:
        return PersistedDocumentChunk(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            index=chunk.chunk_index,
            text=chunk.text,
            strategy=chunk.strategy,  # type: ignore[arg-type]
            start_offset=chunk.start_offset,
            end_offset=chunk.end_offset,
            metadata=chunk.chunk_metadata or {},
            embedding_provider=chunk.embedding_provider,
            embedding_model=chunk.embedding_model,
            embedding_dimensions=chunk.embedding_dimensions,
            embedding_token_count=chunk.embedding_token_count,
            embedding_cost_usd=chunk.embedding_cost_usd,
            embedding_vector=chunk.embedding_vector,
            embedded_at=chunk.embedded_at,
            created_at=chunk.created_at,
            updated_at=chunk.updated_at,
        )

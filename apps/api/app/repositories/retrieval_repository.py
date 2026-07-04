from __future__ import annotations

from typing import Sequence

from sqlalchemy import Date, Text, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.domain.retrieval import RetrievalFilters, RetrievedChunk
from apps.api.app.repositories.models import DocumentChunkModel, DocumentModel


class RetrievalRepository:
    async def semantic_search(
        self,
        session: AsyncSession,
        *,
        query_embedding: Sequence[float],
        filters: RetrievalFilters,
        top_k: int,
    ) -> list[RetrievedChunk]:
        distance = DocumentChunkModel.embedding_vector.cosine_distance(list(query_embedding))
        score = (1 - distance).label("semantic_score")
        stmt = (
            select(DocumentChunkModel, DocumentModel, score)
            .join(DocumentModel, DocumentChunkModel.document_id == DocumentModel.document_id)
            .where(DocumentChunkModel.embedding_vector.is_not(None))
            .order_by(distance.asc())
            .limit(top_k)
        )
        stmt = self._apply_filters(stmt, filters)

        result = await session.execute(stmt)
        return [
            self._to_retrieved_chunk(chunk, document, score_value=float(score_value), semantic_score=float(score_value))
            for chunk, document, score_value in result.all()
        ]

    async def keyword_search(
        self,
        session: AsyncSession,
        *,
        query: str,
        filters: RetrievalFilters,
        top_k: int,
    ) -> list[RetrievedChunk]:
        content = func.concat_ws(" ", func.coalesce(DocumentModel.title, ""), DocumentChunkModel.text)
        tsvector = func.to_tsvector("english", content)
        tsquery = func.websearch_to_tsquery("english", query)
        rank = func.ts_rank_cd(tsvector, tsquery).label("keyword_score")

        stmt = (
            select(DocumentChunkModel, DocumentModel, rank)
            .join(DocumentModel, DocumentChunkModel.document_id == DocumentModel.document_id)
            .where(tsvector.op("@@")(tsquery))
            .order_by(rank.desc())
            .limit(top_k)
        )
        stmt = self._apply_filters(stmt, filters)

        result = await session.execute(stmt)
        return [
            self._to_retrieved_chunk(chunk, document, score_value=float(score_value), keyword_score=float(score_value))
            for chunk, document, score_value in result.all()
        ]

    @staticmethod
    def _apply_filters(stmt, filters: RetrievalFilters):
        if filters.document_ids:
            stmt = stmt.where(DocumentModel.document_id.in_(filters.document_ids))

        if filters.company:
            stmt = stmt.where(DocumentModel.attributes["company"].astext == filters.company)

        if filters.document_type:
            stmt = stmt.where(DocumentModel.attributes["document_type"].astext == filters.document_type)

        if filters.source:
            stmt = stmt.where(DocumentModel.attributes["source"].astext == filters.source)

        if filters.date_from:
            stmt = stmt.where(
                cast(DocumentModel.attributes["date"].astext, Date) >= cast(filters.date_from, Date)
            )

        if filters.date_to:
            stmt = stmt.where(
                cast(DocumentModel.attributes["date"].astext, Date) <= cast(filters.date_to, Date)
            )

        if filters.tags:
            stmt = stmt.where(DocumentModel.attributes["tags"].contains(filters.tags))

        return stmt

    @staticmethod
    def _to_retrieved_chunk(
        chunk: DocumentChunkModel,
        document: DocumentModel,
        *,
        score_value: float,
        semantic_score: float | None = None,
        keyword_score: float | None = None,
    ) -> RetrievedChunk:
        page_number = None
        if chunk.chunk_metadata:
            page_number = chunk.chunk_metadata.get("page_number")

        return RetrievedChunk(
            chunk_id=chunk.chunk_id,
            document_id=document.document_id,
            document_title=document.title,
            text=chunk.text,
            score=score_value,
            semantic_score=semantic_score,
            keyword_score=keyword_score,
            page_number=page_number,
            document_metadata=document.attributes or {},
            chunk_metadata=chunk.chunk_metadata or {},
        )

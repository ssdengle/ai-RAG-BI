from __future__ import annotations

from apps.api.app.domain.retrieval import RetrievalFilters, RetrievalMode, RetrievalResult, RetrievedChunk
from apps.api.app.rag.embeddings import EmbeddingProvider
from apps.api.app.repositories.retrieval_repository import RetrievalRepository
from apps.api.app.services.citation_service import CitationSelectionService
from apps.api.app.services.reranking_service import DefaultReranker


class RetrievalService:
    def __init__(
        self,
        *,
        retrieval_repository: RetrievalRepository,
        embedding_provider: EmbeddingProvider,
        reranker: DefaultReranker,
        citation_selector: CitationSelectionService,
    ) -> None:
        self._retrieval_repository = retrieval_repository
        self._embedding_provider = embedding_provider
        self._reranker = reranker
        self._citation_selector = citation_selector

    async def retrieve(
        self,
        session,
        *,
        query: str,
        mode: RetrievalMode,
        filters: RetrievalFilters,
        top_k: int,
    ) -> RetrievalResult:
        candidate_limit = max(top_k * 2, top_k)

        if mode == "semantic":
            chunks = await self._semantic_retrieve(
                session,
                query=query,
                filters=filters,
                top_k=candidate_limit,
            )
        elif mode == "keyword":
            chunks = await self._retrieval_repository.keyword_search(
                session,
                query=query,
                filters=filters,
                top_k=candidate_limit,
            )
        else:
            semantic_chunks = await self._semantic_retrieve(
                session,
                query=query,
                filters=filters,
                top_k=candidate_limit,
            )
            keyword_chunks = await self._retrieval_repository.keyword_search(
                session,
                query=query,
                filters=filters,
                top_k=candidate_limit,
            )
            chunks = _merge_hybrid_results(semantic_chunks, keyword_chunks)

        reranked_chunks = self._reranker.rerank(query=query, chunks=chunks, top_k=top_k)
        citations = self._citation_selector.select(reranked_chunks)

        return RetrievalResult(
            mode=mode,
            query=query,
            chunks=reranked_chunks,
            citations=citations,
            total_candidates=len(chunks),
        )

    async def _semantic_retrieve(self, session, *, query: str, filters: RetrievalFilters, top_k: int):
        embedding_result = await self._embedding_provider.embed_texts([query])
        query_embedding = embedding_result.vectors[0]
        return await self._retrieval_repository.semantic_search(
            session,
            query_embedding=query_embedding,
            filters=filters,
            top_k=top_k,
        )


def _merge_hybrid_results(
    semantic_chunks: list[RetrievedChunk],
    keyword_chunks: list[RetrievedChunk],
) -> list[RetrievedChunk]:
    merged: dict[str, RetrievedChunk] = {}

    for chunk in semantic_chunks:
        merged[chunk.chunk_id] = chunk

    for chunk in keyword_chunks:
        existing = merged.get(chunk.chunk_id)
        if existing is None:
            merged[chunk.chunk_id] = chunk
            continue

        semantic_score = existing.semantic_score or existing.score or 0.0
        keyword_score = chunk.keyword_score or chunk.score or 0.0
        hybrid_score = round((semantic_score * 0.6) + (keyword_score * 0.4), 6)
        merged[chunk.chunk_id] = RetrievedChunk(
            **{
                **existing.__dict__,
                "score": hybrid_score,
                "keyword_score": keyword_score,
                "semantic_score": semantic_score,
            }
        )

    for chunk_id, chunk in list(merged.items()):
        if chunk.semantic_score is None and chunk.keyword_score is not None:
            merged[chunk_id] = RetrievedChunk(
                **{
                    **chunk.__dict__,
                    "score": chunk.keyword_score,
                }
            )

    return sorted(merged.values(), key=lambda item: item.score, reverse=True)

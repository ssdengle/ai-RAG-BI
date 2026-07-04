from __future__ import annotations

import asyncio

from apps.api.app.domain.retrieval import RetrievalFilters, RetrievedChunk
from apps.api.app.rag.embeddings import EmbeddingBatchResult, EmbeddingBatchUsage
from apps.api.app.services.citation_service import CitationSelectionService
from apps.api.app.services.reranking_service import DefaultReranker
from apps.api.app.services.retrieval_service import RetrievalService


class _FakeEmbeddingProvider:
    async def embed_texts(self, texts):
        return EmbeddingBatchResult(
            vectors=[[0.1, 0.2, 0.3] for _ in texts],
            provider="openai",
            model="text-embedding-3-small",
            dimensions=3,
            usage=EmbeddingBatchUsage(prompt_tokens=3),
        )


class _FakeRetrievalRepository:
    def __init__(self) -> None:
        self.last_semantic_filters = None
        self.last_keyword_filters = None

    async def semantic_search(self, session, *, query_embedding, filters, top_k):
        self.last_semantic_filters = filters
        return [
            RetrievedChunk(
                chunk_id="s1",
                document_id="doc-1",
                document_title="Doc 1",
                text="Revenue growth accelerated in Q1.",
                score=0.92,
                semantic_score=0.92,
                document_metadata={"company": "Acme"},
                chunk_metadata={"page_number": 1},
            )
        ]

    async def keyword_search(self, session, *, query, filters, top_k):
        self.last_keyword_filters = filters
        return [
            RetrievedChunk(
                chunk_id="k1",
                document_id="doc-2",
                document_title="Doc 2",
                text="Operating margin improved after restructuring.",
                score=0.67,
                keyword_score=0.67,
                document_metadata={"source": "10-K"},
                chunk_metadata={},
            )
        ]


def test_semantic_retrieval_uses_query_embedding() -> None:
    repository = _FakeRetrievalRepository()
    service = RetrievalService(
        retrieval_repository=repository,
        embedding_provider=_FakeEmbeddingProvider(),
        reranker=DefaultReranker(),
        citation_selector=CitationSelectionService(),
    )

    result = asyncio.run(
        service.retrieve(
            None,
            query="What happened to revenue?",
            mode="semantic",
            filters=RetrievalFilters(),
            top_k=3,
        )
    )

    assert result.mode == "semantic"
    assert result.chunks[0].chunk_id == "s1"


def test_keyword_retrieval_uses_keyword_repository_path() -> None:
    repository = _FakeRetrievalRepository()
    service = RetrievalService(
        retrieval_repository=repository,
        embedding_provider=_FakeEmbeddingProvider(),
        reranker=DefaultReranker(),
        citation_selector=CitationSelectionService(),
    )

    result = asyncio.run(
        service.retrieve(
            None,
            query="operating margin",
            mode="keyword",
            filters=RetrievalFilters(),
            top_k=3,
        )
    )

    assert result.mode == "keyword"
    assert result.chunks[0].chunk_id == "k1"


def test_hybrid_retrieval_merges_semantic_and_keyword_results() -> None:
    repository = _FakeRetrievalRepository()
    service = RetrievalService(
        retrieval_repository=repository,
        embedding_provider=_FakeEmbeddingProvider(),
        reranker=DefaultReranker(),
        citation_selector=CitationSelectionService(),
    )

    result = asyncio.run(
        service.retrieve(
            None,
            query="revenue margin",
            mode="hybrid",
            filters=RetrievalFilters(),
            top_k=5,
        )
    )

    assert result.mode == "hybrid"
    assert {chunk.chunk_id for chunk in result.chunks} == {"s1", "k1"}


def test_metadata_filters_are_forwarded_to_repository() -> None:
    repository = _FakeRetrievalRepository()
    service = RetrievalService(
        retrieval_repository=repository,
        embedding_provider=_FakeEmbeddingProvider(),
        reranker=DefaultReranker(),
        citation_selector=CitationSelectionService(),
    )
    filters = RetrievalFilters(
        document_ids=["doc-1"],
        company="Acme",
        document_type="10-K",
        source="edgar",
        date_from="2024-01-01",
        date_to="2024-12-31",
        tags=["finance"],
    )

    asyncio.run(
        service.retrieve(
            None,
            query="revenue growth",
            mode="semantic",
            filters=filters,
            top_k=3,
        )
    )

    assert repository.last_semantic_filters == filters

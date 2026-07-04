from apps.api.app.domain.retrieval import RetrievedChunk
from apps.api.app.services.reranking_service import DefaultReranker


def test_default_reranker_promotes_query_overlap() -> None:
    reranker = DefaultReranker()
    chunks = [
        RetrievedChunk(
            chunk_id="c1",
            document_id="doc-1",
            document_title="Doc 1",
            text="Cash flow improved significantly.",
            score=0.9,
        ),
        RetrievedChunk(
            chunk_id="c2",
            document_id="doc-1",
            document_title="Doc 1",
            text="Revenue growth accelerated in the quarter.",
            score=0.8,
        ),
    ]

    reranked = reranker.rerank(query="revenue growth", chunks=chunks, top_k=2)

    assert reranked[0].chunk_id == "c2"
    assert reranked[0].rerank_score is not None

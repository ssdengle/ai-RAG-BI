from __future__ import annotations

import re

from apps.api.app.domain.retrieval import RetrievedChunk


class DefaultReranker:
    def rerank(
        self,
        *,
        query: str,
        chunks: list[RetrievedChunk],
        top_k: int,
    ) -> list[RetrievedChunk]:
        query_terms = _tokenize(query)
        reranked: list[RetrievedChunk] = []

        for chunk in chunks:
            chunk_terms = _tokenize(chunk.text)
            overlap_ratio = _compute_overlap(query_terms, chunk_terms)
            base_score = chunk.score
            rerank_score = round((base_score * 0.75) + (overlap_ratio * 0.25), 6)
            reranked.append(
                RetrievedChunk(
                    **{
                        **chunk.__dict__,
                        "score": rerank_score,
                        "rerank_score": rerank_score,
                    }
                )
            )

        reranked.sort(key=lambda item: item.score, reverse=True)
        return reranked[:top_k]


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[A-Za-z0-9]+", text.lower()) if len(token) > 1}


def _compute_overlap(query_terms: set[str], chunk_terms: set[str]) -> float:
    if not query_terms or not chunk_terms:
        return 0.0

    overlap = len(query_terms.intersection(chunk_terms))
    return overlap / len(query_terms)

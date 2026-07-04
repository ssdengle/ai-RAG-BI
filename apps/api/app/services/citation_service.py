from __future__ import annotations

from apps.api.app.domain.retrieval import Citation, RetrievedChunk


class CitationSelectionService:
    def select(self, chunks: list[RetrievedChunk], *, max_citations: int = 5) -> list[Citation]:
        citations: list[Citation] = []

        for chunk in chunks[:max_citations]:
            citations.append(
                Citation(
                    document_id=chunk.document_id,
                    title=chunk.document_title,
                    chunk_id=chunk.chunk_id,
                    page_number=chunk.page_number,
                    score=chunk.score,
                    snippet=_build_snippet(chunk.text),
                )
            )

        return citations


def _build_snippet(text: str, *, limit: int = 240) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[: limit - 3].rstrip()}..."

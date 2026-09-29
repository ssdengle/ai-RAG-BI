from __future__ import annotations

import time
from typing import Any

from apps.api.app.domain.retrieval import Citation
from apps.api.app.domain.workflows import AgentExecutionMetadata, AgentResult


def citations_to_dicts(citations: list[Citation]) -> list[dict[str, Any]]:
    return [
        {
            "document_id": citation.document_id,
            "title": citation.title,
            "chunk_id": citation.chunk_id,
            "page_number": citation.page_number,
            "score": citation.score,
            "snippet": citation.snippet,
        }
        for citation in citations
    ]


def merge_citations(existing: list[dict[str, Any]], new_citations: list[Citation]) -> list[dict[str, Any]]:
    merged = {f"{item['document_id']}:{item['chunk_id']}": item for item in existing}
    for citation in new_citations:
        key = f"{citation.document_id}:{citation.chunk_id}"
        merged[key] = {
            "document_id": citation.document_id,
            "title": citation.title,
            "chunk_id": citation.chunk_id,
            "page_number": citation.page_number,
            "score": citation.score,
            "snippet": citation.snippet,
        }
    return list(merged.values())


def agent_result_to_state_update(result: AgentResult) -> dict[str, Any]:
    return {
        "agent_outputs": {result.agent: result.output},
        "confidence": result.confidence,
        "citations": citations_to_dicts(result.citations),
    }


class AgentTimer:
    def __init__(self) -> None:
        self._start = time.perf_counter()

    @property
    def elapsed_ms(self) -> float:
        return round((time.perf_counter() - self._start) * 1000, 2)


def build_metadata(
    timer: AgentTimer,
    *,
    tool_calls: list[str],
    retrieval_statistics: dict[str, Any] | None = None,
    token_usage: dict[str, int] | None = None,
) -> AgentExecutionMetadata:
    return AgentExecutionMetadata(
        latency_ms=timer.elapsed_ms,
        tool_calls=tool_calls,
        token_usage=token_usage,
        retrieval_statistics=retrieval_statistics or {},
    )

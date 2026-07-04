from __future__ import annotations

import asyncio

from apps.api.app.domain.retrieval import RetrievalFilters, RetrievalResult, RetrievedChunk
from apps.api.app.rag.llm import ChatCompletionResult
from apps.api.app.services.citation_service import CitationSelectionService
from apps.api.app.services.context_assembly_service import ContextAssemblyService
from apps.api.app.services.prompt_service import GroundedPromptService
from apps.api.app.services.question_answering_service import QuestionAnsweringService


class _FakeRetrievalService:
    def __init__(self, *, empty: bool = False) -> None:
        self.empty = empty

    async def retrieve(self, session, *, query, mode, filters, top_k):
        chunks = []
        citations = []
        if not self.empty:
            chunk = RetrievedChunk(
                chunk_id="chunk-1",
                document_id="doc-1",
                document_title="Quarterly Report",
                text="Revenue increased in Q1.",
                score=0.91,
                semantic_score=0.91,
                page_number=2,
            )
            chunks = [chunk]
            citations = CitationSelectionService().select(chunks)

        return RetrievalResult(
            mode=mode,
            query=query,
            chunks=chunks,
            citations=citations,
            total_candidates=len(chunks),
        )


class _FakeChatProvider:
    async def complete(self, messages):
        return ChatCompletionResult(
            text="Revenue increased in Q1 based on the retrieved report.",
            provider="openai",
            model="gpt-4o-mini",
            finish_reason="stop",
        )


def test_question_answering_service_returns_grounded_answer_with_mocked_llm() -> None:
    service = QuestionAnsweringService(
        retrieval_service=_FakeRetrievalService(),
        context_assembly_service=ContextAssemblyService(),
        prompt_service=GroundedPromptService(),
        chat_provider=_FakeChatProvider(),
    )

    result = asyncio.run(
        service.answer(
            None,
            question="What happened to revenue?",
            mode="hybrid",
            filters=RetrievalFilters(),
            top_k=3,
        )
    )

    assert "Revenue increased" in result.answer
    assert result.citations
    assert result.confidence > 0


def test_question_answering_service_handles_empty_results_without_calling_llm() -> None:
    service = QuestionAnsweringService(
        retrieval_service=_FakeRetrievalService(empty=True),
        context_assembly_service=ContextAssemblyService(),
        prompt_service=GroundedPromptService(),
        chat_provider=_FakeChatProvider(),
    )

    result = asyncio.run(
        service.answer(
            None,
            question="What happened to revenue?",
            mode="hybrid",
            filters=RetrievalFilters(),
            top_k=3,
        )
    )

    assert result.answer == "Not enough information in the retrieved context."
    assert result.citations == []
    assert result.confidence == 0.0

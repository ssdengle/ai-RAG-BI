from __future__ import annotations

from apps.api.app.domain.retrieval import (
    QuestionAnswerResult,
    RetrievalFilters,
    RetrievalMode,
)
from apps.api.app.rag.llm import ChatCompletionProvider
from apps.api.app.services.context_assembly_service import ContextAssemblyService
from apps.api.app.services.prompt_service import GroundedPromptService
from apps.api.app.services.retrieval_service import RetrievalService


class QuestionAnsweringService:
    def __init__(
        self,
        *,
        retrieval_service: RetrievalService,
        context_assembly_service: ContextAssemblyService,
        prompt_service: GroundedPromptService,
        chat_provider: ChatCompletionProvider,
    ) -> None:
        self._retrieval_service = retrieval_service
        self._context_assembly_service = context_assembly_service
        self._prompt_service = prompt_service
        self._chat_provider = chat_provider

    async def answer(
        self,
        session,
        *,
        question: str,
        mode: RetrievalMode,
        filters: RetrievalFilters,
        top_k: int,
    ) -> QuestionAnswerResult:
        retrieval_result = await self._retrieval_service.retrieve(
            session,
            query=question,
            mode=mode,
            filters=filters,
            top_k=top_k,
        )

        context = self._context_assembly_service.assemble(
            chunks=retrieval_result.chunks,
            citations=retrieval_result.citations,
        )

        if not context.text.strip():
            return QuestionAnswerResult(
                answer="Not enough information in the retrieved context.",
                citations=[],
                confidence=0.0,
                retrieval=retrieval_result,
                context=context,
                llm_provider=None,
                llm_model=None,
                finish_reason=None,
            )

        messages = self._prompt_service.build_messages(question=question, context=context)
        llm_result = await self._chat_provider.complete(messages)
        confidence = _compute_confidence(retrieval_result.chunks)

        return QuestionAnswerResult(
            answer=llm_result.text.strip(),
            citations=context.citations,
            confidence=confidence,
            retrieval=retrieval_result,
            context=context,
            llm_provider=llm_result.provider,
            llm_model=llm_result.model,
            finish_reason=llm_result.finish_reason,
        )


def _compute_confidence(chunks) -> float:
    if not chunks:
        return 0.0

    top_scores = [max(chunk.score, 0.0) for chunk in chunks[:3]]
    return round(min(sum(top_scores) / len(top_scores), 1.0), 4)

from __future__ import annotations

from typing import Any

from apps.api.app.core.cache import CacheClient, build_cache_key
from apps.api.app.core.metrics import record_cache_hit, record_cache_miss
from apps.api.app.core.config import CacheSettings
from apps.api.app.domain.retrieval import QuestionAnswerResult, RetrievalFilters, RetrievalMode
from apps.api.app.services.question_answering_service import QuestionAnsweringService


class CachingQuestionAnsweringService:
    """Caches grounded Q&A responses at the service boundary."""

    def __init__(self, inner: QuestionAnsweringService, cache: CacheClient, settings: CacheSettings) -> None:
        self._inner = inner
        self._cache = cache
        self._settings = settings

    async def answer(
        self,
        session,
        *,
        question: str,
        mode: RetrievalMode,
        filters: RetrievalFilters,
        top_k: int,
    ) -> QuestionAnswerResult:
        cache_key = build_cache_key(
            "qa",
            {"question": question, "mode": mode, "filters": filters, "top_k": top_k},
        )
        cached = await self._cache.get_json(cache_key)
        if cached is not None:
            record_cache_hit("qa")
            return _qa_from_dict(cached)
        record_cache_miss("qa")

        result = await self._inner.answer(
            session,
            question=question,
            mode=mode,
            filters=filters,
            top_k=top_k,
        )
        await self._cache.set_json(cache_key, _qa_to_dict(result), ttl_seconds=self._settings.qa_ttl_seconds)
        return result


def _qa_to_dict(result: QuestionAnswerResult) -> dict[str, Any]:
    from apps.api.app.integrations.caching.retrieval_cache import _retrieval_to_dict

    return {
        "answer": result.answer,
        "citations": [citation.__dict__ for citation in result.citations],
        "confidence": result.confidence,
        "retrieval": _retrieval_to_dict(result.retrieval),
        "context": result.context.__dict__,
        "llm_provider": result.llm_provider,
        "llm_model": result.llm_model,
        "finish_reason": result.finish_reason,
    }


def _qa_from_dict(payload: dict[str, Any]) -> QuestionAnswerResult:
    from apps.api.app.domain.retrieval import AssembledContext, Citation
    from apps.api.app.integrations.caching.retrieval_cache import _retrieval_from_dict

    context_payload = payload.get("context") or {}
    return QuestionAnswerResult(
        answer=payload["answer"],
        citations=[Citation(**citation) for citation in payload.get("citations", [])],
        confidence=float(payload.get("confidence", 0.0)),
        retrieval=_retrieval_from_dict(payload["retrieval"]),
        context=AssembledContext(**context_payload),
        llm_provider=payload.get("llm_provider"),
        llm_model=payload.get("llm_model"),
        finish_reason=payload.get("finish_reason"),
    )

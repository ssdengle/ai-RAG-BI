from __future__ import annotations

from typing import Any

from apps.api.app.core.cache import CacheClient, build_cache_key
from apps.api.app.core.metrics import record_cache_hit, record_cache_miss
from apps.api.app.core.config import CacheSettings
from apps.api.app.domain.retrieval import RetrievalFilters, RetrievalMode, RetrievalResult
from apps.api.app.services.retrieval_service import RetrievalService


class CachingRetrievalService:
    """Transparent wrapper that caches retrieval results without changing business logic."""

    def __init__(self, inner: RetrievalService, cache: CacheClient, settings: CacheSettings) -> None:
        self._inner = inner
        self._cache = cache
        self._settings = settings

    async def retrieve(
        self,
        session,
        *,
        query: str,
        mode: RetrievalMode,
        filters: RetrievalFilters,
        top_k: int,
    ) -> RetrievalResult:
        cache_key = build_cache_key(
            "retrieval",
            {
                "query": query,
                "mode": mode,
                "filters": filters,
                "top_k": top_k,
            },
        )
        cached = await self._cache.get_json(cache_key)
        if cached is not None:
            record_cache_hit("retrieval")
            return _retrieval_from_dict(cached)
        record_cache_miss("retrieval")

        result = await self._inner.retrieve(
            session,
            query=query,
            mode=mode,
            filters=filters,
            top_k=top_k,
        )
        await self._cache.set_json(cache_key, _retrieval_to_dict(result), ttl_seconds=self._settings.retrieval_ttl_seconds)
        return result


def _retrieval_to_dict(result: RetrievalResult) -> dict[str, Any]:
    return {
        "mode": result.mode,
        "query": result.query,
        "chunks": [chunk.__dict__ for chunk in result.chunks],
        "citations": [citation.__dict__ for citation in result.citations],
        "total_candidates": result.total_candidates,
    }


def _retrieval_from_dict(payload: dict[str, Any]) -> RetrievalResult:
    from apps.api.app.domain.retrieval import Citation, RetrievedChunk

    return RetrievalResult(
        mode=payload["mode"],
        query=payload["query"],
        chunks=[RetrievedChunk(**chunk) for chunk in payload.get("chunks", [])],
        citations=[Citation(**citation) for citation in payload.get("citations", [])],
        total_candidates=int(payload.get("total_candidates", 0)),
    )

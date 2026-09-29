from __future__ import annotations

from apps.api.app.core.cache import CacheClient, build_cache_key
from apps.api.app.core.metrics import record_cache_hit, record_cache_miss
from apps.api.app.core.config import CacheSettings
from apps.api.app.rag.embeddings import EmbeddingBatchResult, EmbeddingProvider


class CachingEmbeddingProvider:
    """Caches embedding batch results at the provider boundary."""

    def __init__(self, inner: EmbeddingProvider, cache: CacheClient, settings: CacheSettings) -> None:
        self._inner = inner
        self._cache = cache
        self._settings = settings

    async def embed_texts(self, texts: list[str]) -> EmbeddingBatchResult:
        cache_key = build_cache_key("embedding", {"texts": texts})
        cached = await self._cache.get_json(cache_key)
        if cached is not None:
            record_cache_hit("embedding")
            return _embedding_from_dict(cached)
        record_cache_miss("embedding")

        result = await self._inner.embed_texts(texts)
        await self._cache.set_json(cache_key, _embedding_to_dict(result), ttl_seconds=self._settings.embedding_ttl_seconds)
        return result


def _embedding_to_dict(result: EmbeddingBatchResult) -> dict:
    return {
        "vectors": result.vectors,
        "provider": result.provider,
        "model": result.model,
        "dimensions": result.dimensions,
        "usage": {
            "prompt_tokens": result.usage.prompt_tokens,
            "total_tokens": result.usage.total_tokens,
        },
    }


def _embedding_from_dict(payload: dict) -> EmbeddingBatchResult:
    from apps.api.app.rag.embeddings import EmbeddingBatchUsage

    usage_payload = payload.get("usage") or {}
    return EmbeddingBatchResult(
        vectors=payload["vectors"],
        provider=payload["provider"],
        model=payload["model"],
        dimensions=payload["dimensions"],
        usage=EmbeddingBatchUsage(
            prompt_tokens=usage_payload.get("prompt_tokens"),
            total_tokens=usage_payload.get("total_tokens"),
        ),
    )

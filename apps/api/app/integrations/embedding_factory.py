from __future__ import annotations

from typing import Optional

from apps.api.app.core.cache import CacheClient
from apps.api.app.core.config import Settings
from apps.api.app.core.errors import ConfigurationError
from apps.api.app.integrations.caching.embedding_cache import CachingEmbeddingProvider
from apps.api.app.integrations.observability import TracedEmbeddingProvider
from apps.api.app.integrations.openai_embeddings import OpenAIEmbeddingProvider
from apps.api.app.rag.embeddings import EmbeddingProvider


def build_embedding_provider(
    settings: Settings,
    *,
    cache_client: Optional[CacheClient] = None,
) -> EmbeddingProvider:
    provider_name = settings.llm.provider.lower().strip()

    if provider_name == "openai":
        provider: EmbeddingProvider = OpenAIEmbeddingProvider(settings.llm)
    else:
        raise ConfigurationError(
            f"Unsupported embedding provider '{settings.llm.provider}'.",
            code="unsupported_embedding_provider",
        )

    if settings.telemetry.enabled:
        provider = TracedEmbeddingProvider(provider)
    if settings.cache.enabled and cache_client is not None:
        provider = CachingEmbeddingProvider(provider, cache_client, settings.cache)
    return provider

from __future__ import annotations

from apps.api.app.core.config import Settings
from apps.api.app.core.errors import ConfigurationError
from apps.api.app.integrations.openai_embeddings import OpenAIEmbeddingProvider
from apps.api.app.rag.embeddings import EmbeddingProvider


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    provider_name = settings.llm.provider.lower().strip()

    if provider_name == "openai":
        return OpenAIEmbeddingProvider(settings.llm)

    raise ConfigurationError(
        f"Unsupported embedding provider '{settings.llm.provider}'.",
        code="unsupported_embedding_provider",
    )

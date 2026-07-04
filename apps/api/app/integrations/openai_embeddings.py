from __future__ import annotations

from typing import Any, Optional

from apps.api.app.core.config import LLMSettings
from apps.api.app.core.errors import ConfigurationError, ExternalServiceError
from apps.api.app.rag.embeddings import EmbeddingBatchResult, EmbeddingBatchUsage, EmbeddingProvider


_OPENAI_EMBEDDING_PRICING_PER_1M_TOKENS = {
    "text-embedding-3-small": 0.02,
    "text-embedding-3-large": 0.13,
    "text-embedding-ada-002": 0.10,
}


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, settings: LLMSettings, client: Optional[Any] = None) -> None:
        if settings.api_key is None or not settings.api_key.get_secret_value():
            raise ConfigurationError(
                "OpenAI embedding provider requires an API key.",
                code="openai_api_key_missing",
            )

        self._settings = settings
        self._client = client or self._build_client(settings)

    async def embed_texts(self, texts: list[str]) -> EmbeddingBatchResult:
        try:
            response = await self._client.embeddings.create(
                model=self._settings.embedding_model,
                input=texts,
                dimensions=self._settings.embedding_dimensions,
            )
        except Exception as exc:
            raise ExternalServiceError(
                "OpenAI embedding request failed.",
                details=str(exc),
                code="openai_embedding_failed",
            ) from exc

        sorted_data = sorted(response.data, key=lambda item: item.index)
        vectors = [list(item.embedding) for item in sorted_data]
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", None) if usage is not None else None
        total_cost_usd = _estimate_openai_embedding_cost(
            model=self._settings.embedding_model,
            prompt_tokens=prompt_tokens,
        )

        return EmbeddingBatchResult(
            vectors=vectors,
            provider="openai",
            model=self._settings.embedding_model,
            dimensions=len(vectors[0]) if vectors else self._settings.embedding_dimensions,
            usage=EmbeddingBatchUsage(
                prompt_tokens=prompt_tokens,
                total_cost_usd=total_cost_usd,
            ),
        )

    @staticmethod
    def _build_client(settings: LLMSettings) -> Any:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise ConfigurationError(
                "The OpenAI provider requires the 'openai' package.",
                code="openai_package_missing",
            ) from exc

        return AsyncOpenAI(
            api_key=settings.api_key.get_secret_value(),
            base_url=settings.base_url,
            timeout=settings.timeout_seconds,
        )


def _estimate_openai_embedding_cost(*, model: str, prompt_tokens: int | None) -> float | None:
    if prompt_tokens is None:
        return None

    price_per_1m_tokens = _OPENAI_EMBEDDING_PRICING_PER_1M_TOKENS.get(model)
    if price_per_1m_tokens is None:
        return None

    return round((prompt_tokens / 1_000_000) * price_per_1m_tokens, 8)

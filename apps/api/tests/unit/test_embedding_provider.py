from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from apps.api.app.core.config import LLMSettings
from apps.api.app.core.errors import ConfigurationError
from apps.api.app.integrations.embedding_factory import build_embedding_provider
from apps.api.app.integrations.openai_embeddings import OpenAIEmbeddingProvider
from apps.api.tests.conftest import build_test_settings


class _FakeEmbeddingsClient:
    async def create(self, **kwargs):
        return SimpleNamespace(
            data=[
                SimpleNamespace(index=0, embedding=[0.1, 0.2]),
                SimpleNamespace(index=1, embedding=[0.3, 0.4]),
            ],
            usage=SimpleNamespace(prompt_tokens=20),
        )


class _FakeOpenAIClient:
    def __init__(self) -> None:
        self.embeddings = _FakeEmbeddingsClient()


def test_openai_embedding_provider_returns_vectors_and_usage() -> None:
    provider = OpenAIEmbeddingProvider(
        LLMSettings(
            provider="openai",
            model="gpt-4o-mini",
            api_key="secret-key",
            base_url=None,
            timeout_seconds=30,
            embedding_model="text-embedding-3-small",
            embedding_dimensions=2,
            embedding_batch_size=8,
            embedding_max_retries=2,
        ),
        client=_FakeOpenAIClient(),
    )

    result = asyncio.run(provider.embed_texts(["Alpha", "Beta"]))

    assert result.provider == "openai"
    assert result.model == "text-embedding-3-small"
    assert result.vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert result.usage.prompt_tokens == 20


def test_embedding_factory_returns_openai_provider() -> None:
    settings = build_test_settings()
    settings.llm = LLMSettings(
        provider="openai",
        model="gpt-4o-mini",
        api_key="secret-key",
        base_url=None,
        timeout_seconds=30,
        embedding_model="text-embedding-3-small",
        embedding_dimensions=1536,
        embedding_batch_size=32,
        embedding_max_retries=3,
    )

    provider = build_embedding_provider(settings)

    assert isinstance(provider, OpenAIEmbeddingProvider)


def test_embedding_factory_rejects_unknown_provider() -> None:
    settings = build_test_settings()
    settings.llm.provider = "unknown-provider"

    with pytest.raises(ConfigurationError):
        build_embedding_provider(settings)

from __future__ import annotations

from typing import Optional

from apps.api.app.core.config import Settings
from apps.api.app.core.errors import ConfigurationError
from apps.api.app.integrations.observability import TracedChatProvider
from apps.api.app.integrations.openai_chat import OpenAIChatProvider
from apps.api.app.rag.llm import ChatCompletionProvider


def build_chat_provider(settings: Settings) -> ChatCompletionProvider:
    provider_name = settings.llm.provider.lower().strip()

    if provider_name == "openai":
        provider: ChatCompletionProvider = OpenAIChatProvider(settings.llm)
    else:
        raise ConfigurationError(
            f"Unsupported chat provider '{settings.llm.provider}'.",
            code="unsupported_chat_provider",
        )

    if settings.telemetry.enabled:
        provider = TracedChatProvider(provider)
    return provider

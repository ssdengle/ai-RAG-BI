from __future__ import annotations

from apps.api.app.core.config import Settings
from apps.api.app.core.errors import ConfigurationError
from apps.api.app.integrations.openai_chat import OpenAIChatProvider
from apps.api.app.rag.llm import ChatCompletionProvider


def build_chat_provider(settings: Settings) -> ChatCompletionProvider:
    provider_name = settings.llm.provider.lower().strip()

    if provider_name == "openai":
        return OpenAIChatProvider(settings.llm)

    raise ConfigurationError(
        f"Unsupported chat provider '{settings.llm.provider}'.",
        code="unsupported_chat_provider",
    )

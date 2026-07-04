from __future__ import annotations

from typing import Any, Optional

from apps.api.app.core.config import LLMSettings
from apps.api.app.core.errors import ConfigurationError, ExternalServiceError
from apps.api.app.rag.llm import ChatCompletionProvider, ChatCompletionResult, ChatMessage


class OpenAIChatProvider(ChatCompletionProvider):
    def __init__(self, settings: LLMSettings, client: Optional[Any] = None) -> None:
        if settings.api_key is None or not settings.api_key.get_secret_value():
            raise ConfigurationError(
                "OpenAI chat provider requires an API key.",
                code="openai_api_key_missing",
            )

        self._settings = settings
        self._client = client or self._build_client(settings)

    async def complete(self, messages: list[ChatMessage]) -> ChatCompletionResult:
        try:
            response = await self._client.chat.completions.create(
                model=self._settings.model,
                messages=[{"role": message.role, "content": message.content} for message in messages],
                temperature=0,
            )
        except Exception as exc:
            raise ExternalServiceError(
                "OpenAI chat completion failed.",
                details=str(exc),
                code="openai_chat_failed",
            ) from exc

        choice = response.choices[0]
        usage = getattr(response, "usage", None)
        return ChatCompletionResult(
            text=choice.message.content or "",
            provider="openai",
            model=self._settings.model,
            finish_reason=getattr(choice, "finish_reason", None),
            prompt_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
            completion_tokens=getattr(usage, "completion_tokens", None) if usage else None,
            total_cost_usd=None,
        )

    @staticmethod
    def _build_client(settings: LLMSettings) -> Any:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise ConfigurationError(
                "The OpenAI chat provider requires the 'openai' package.",
                code="openai_package_missing",
            ) from exc

        return AsyncOpenAI(
            api_key=settings.api_key.get_secret_value(),
            base_url=settings.base_url,
            timeout=settings.timeout_seconds,
        )

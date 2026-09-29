from __future__ import annotations

import time
from typing import Optional

from apps.api.app.core.telemetry import start_span
from apps.api.app.rag.embeddings import EmbeddingBatchResult, EmbeddingProvider
from apps.api.app.rag.llm import ChatCompletionProvider, ChatCompletionResult, ChatMessage


class TracedEmbeddingProvider:
    def __init__(self, inner: EmbeddingProvider) -> None:
        self._inner = inner

    async def embed_texts(self, texts: list[str]) -> EmbeddingBatchResult:
        with start_span("llm.embeddings", attributes={"text_count": len(texts)}):
            return await self._inner.embed_texts(texts)


class TracedChatProvider:
    def __init__(self, inner: ChatCompletionProvider) -> None:
        self._inner = inner

    async def complete(self, messages: list[ChatMessage]) -> ChatCompletionResult:
        with start_span("llm.chat.completion", attributes={"message_count": len(messages)}):
            return await self._inner.complete(messages)

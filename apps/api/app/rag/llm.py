from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ChatCompletionResult:
    text: str
    provider: str
    model: str
    finish_reason: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_cost_usd: Optional[float] = None


class ChatCompletionProvider(Protocol):
    async def complete(self, messages: list[ChatMessage]) -> ChatCompletionResult:
        """Generate a grounded completion from a list of chat messages."""

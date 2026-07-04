from __future__ import annotations

from pathlib import Path

from apps.api.app.domain.retrieval import AssembledContext
from apps.api.app.rag.llm import ChatMessage


class GroundedPromptService:
    def __init__(self, *, prompt_path: Path | None = None) -> None:
        self._prompt_path = prompt_path or Path("libs/prompts/grounded_qa_v1.txt")

    def build_messages(self, *, question: str, context: AssembledContext) -> list[ChatMessage]:
        system_prompt = self._prompt_path.read_text(encoding="utf-8").strip()
        context_text = (
            context.text
            if context.text
            else "No relevant context was retrieved."
        )
        user_prompt = (
            f"Question:\n{question}\n\n"
            f"Retrieved context:\n{context_text}\n\n"
            "Answer using only the retrieved context."
        )
        return [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_prompt),
        ]

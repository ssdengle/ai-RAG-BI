from pathlib import Path

from apps.api.app.domain.retrieval import AssembledContext
from apps.api.app.services.prompt_service import GroundedPromptService


def test_prompt_service_builds_grounded_messages(tmp_path: Path) -> None:
    prompt_file = tmp_path / "grounded_prompt.txt"
    prompt_file.write_text("Use only the provided context.", encoding="utf-8")
    service = GroundedPromptService(prompt_path=prompt_file)

    messages = service.build_messages(
        question="What changed in revenue?",
        context=AssembledContext(
            text="[SOURCE document_id=doc-1] Revenue increased in Q1.",
            citations=[],
            chunk_count=1,
            truncated=False,
        ),
    )

    assert messages[0].role == "system"
    assert "Use only the provided context." in messages[0].content
    assert "What changed in revenue?" in messages[1].content

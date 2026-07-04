from apps.api.app.domain.documents import ChunkingOptions
from apps.api.app.rag.chunkers import RecursiveChunker, SemanticChunker, SlidingWindowChunker


def test_recursive_chunker_splits_large_text() -> None:
    chunker = RecursiveChunker()
    text = "Paragraph one. " * 30

    chunks = chunker.chunk(
        document_id="doc-1",
        text=text,
        options=ChunkingOptions(strategy="recursive", max_chunk_size=120),
    )

    assert len(chunks) > 1
    assert all(len(chunk.text) <= 120 for chunk in chunks)


def test_semantic_chunker_keeps_paragraph_boundaries_when_possible() -> None:
    chunker = SemanticChunker()
    text = (
        "Revenue increased by 12% in Q1.\n\n"
        "Customer churn fell after the onboarding refresh.\n\n"
        "Support backlog remained stable."
    )

    chunks = chunker.chunk(
        document_id="doc-1",
        text=text,
        options=ChunkingOptions(strategy="semantic", max_chunk_size=90),
    )

    assert len(chunks) >= 2
    assert "Revenue increased by 12% in Q1." in chunks[0].text


def test_sliding_window_chunker_creates_overlapping_windows() -> None:
    chunker = SlidingWindowChunker()
    text = " ".join(f"word{index}" for index in range(1, 31))

    chunks = chunker.chunk(
        document_id="doc-1",
        text=text,
        options=ChunkingOptions(
            strategy="sliding_window",
            window_size=10,
            step_size=5,
        ),
    )

    assert len(chunks) == 5
    assert chunks[0].text.split()[:3] == ["word1", "word2", "word3"]
    assert chunks[1].text.split()[0] == "word6"

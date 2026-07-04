from apps.api.app.domain.retrieval import Citation, RetrievedChunk
from apps.api.app.services.context_assembly_service import ContextAssemblyService


def test_context_assembly_deduplicates_and_preserves_attribution() -> None:
    service = ContextAssemblyService()
    chunk = RetrievedChunk(
        chunk_id="chunk-1",
        document_id="doc-1",
        document_title="Quarterly Report",
        text="Revenue increased in Q1.",
        score=0.9,
        page_number=2,
    )

    assembled = service.assemble(
        chunks=[chunk, chunk],
        citations=[
            Citation(
                document_id="doc-1",
                title="Quarterly Report",
                chunk_id="chunk-1",
                page_number=2,
                score=0.9,
                snippet="Revenue increased in Q1.",
            )
        ],
        max_context_characters=2000,
    )

    assert assembled.chunk_count == 1
    assert "document_id=doc-1" in assembled.text
    assert assembled.citations[0].chunk_id == "chunk-1"


def test_context_assembly_handles_empty_results_safely() -> None:
    service = ContextAssemblyService()

    assembled = service.assemble(chunks=[], citations=[])

    assert assembled.text == ""
    assert assembled.chunk_count == 0
    assert assembled.citations == []

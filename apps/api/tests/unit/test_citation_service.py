from apps.api.app.domain.retrieval import RetrievedChunk
from apps.api.app.services.citation_service import CitationSelectionService


def test_citation_service_returns_supporting_chunk_metadata() -> None:
    service = CitationSelectionService()
    citations = service.select(
        [
            RetrievedChunk(
                chunk_id="chunk-1",
                document_id="doc-1",
                document_title="Quarterly Report",
                text="Revenue increased by 12 percent year over year.",
                score=0.91,
                page_number=3,
            )
        ]
    )

    assert citations[0].document_id == "doc-1"
    assert citations[0].chunk_id == "chunk-1"
    assert citations[0].page_number == 3
    assert "Revenue increased" in citations[0].snippet

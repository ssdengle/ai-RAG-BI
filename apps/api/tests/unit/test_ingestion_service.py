from apps.api.app.domain.documents import ChunkingOptions
from apps.api.app.rag.parsers import HtmlParser, MarkdownParser, PlainTextParser, build_default_parser_registry
from apps.api.app.rag.service import DocumentIngestionService


def test_plain_text_parser_extracts_text() -> None:
    parser = PlainTextParser()

    parsed = parser.parse("notes.txt", "text/plain", b"Alpha\nBeta")

    assert parsed.text == "Alpha\nBeta"
    assert parsed.title is None


def test_markdown_parser_extracts_heading_as_title() -> None:
    parser = MarkdownParser()

    parsed = parser.parse("briefing.md", "text/markdown", b"# Revenue Overview\n\nContent")

    assert parsed.title == "Revenue Overview"
    assert parsed.extracted_metadata["format"] == "markdown"


def test_html_parser_extracts_title_and_visible_text() -> None:
    parser = HtmlParser()

    parsed = parser.parse(
        "report.html",
        "text/html",
        (
            b"<html><head><title>Quarterly Report</title></head>"
            b"<body><script>ignore()</script><h1>Revenue</h1><p>Growth accelerated.</p></body></html>"
        ),
    )

    assert parsed.title == "Quarterly Report"
    assert "Revenue" in parsed.text
    assert "ignore()" not in parsed.text


def test_parser_registry_resolves_by_extension() -> None:
    registry = build_default_parser_registry()

    parser = registry.resolve("analysis.md", None)

    assert isinstance(parser, MarkdownParser)


def test_document_ingestion_service_returns_metadata_and_chunks() -> None:
    service = DocumentIngestionService()

    result = service.ingest(
        filename="analysis.txt",
        content_type="text/plain",
        content=b"Revenue rose in Q1.\n\nOperating margin improved.\n\nCash flow remained stable.",
        options=ChunkingOptions(strategy="semantic", max_chunk_size=60),
    )

    assert result.metadata.filename == "analysis.txt"
    assert result.metadata.source_format == "txt"
    assert result.metadata.word_count > 0
    assert result.chunks
    assert all(chunk.document_id == result.metadata.document_id for chunk in result.chunks)

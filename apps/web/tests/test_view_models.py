from __future__ import annotations

from datetime import datetime, timezone

from apps.web.streamlit_app.api_client.models import PaginatedDocumentList, DocumentSummary
from apps.web.streamlit_app.utils.formatting import format_bytes, format_percent, truncate_text
from apps.web.streamlit_app.view_models.documents import build_document_browse_view_model


def test_format_helpers() -> None:
    assert format_bytes(2048) == "2.0 KB"
    assert format_percent(0.812) == "81.2%"
    assert truncate_text("abcdefghij", 5) == "abcd…"


def test_build_document_browse_view_model_maps_page() -> None:
    now = datetime.now(timezone.utc)
    page = PaginatedDocumentList(
        items=[
            DocumentSummary(
                document_id="doc-1",
                filename="report.pdf",
                extension=".pdf",
                mime_type="application/pdf",
                checksum_sha256="abc",
                size_bytes=100,
                title="Report",
                source_format="pdf",
                chunk_count=3,
                indexing_status="indexed",
                created_at=now,
                updated_at=now,
            )
        ],
        total=1,
        page=1,
        page_size=20,
        total_pages=1,
    )
    vm = build_document_browse_view_model(page)
    assert vm.total == 1
    assert vm.documents[0]["document_id"] == "doc-1"

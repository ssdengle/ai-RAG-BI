from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.web.streamlit_app.api_client import PlatformApiClient
from apps.web.streamlit_app.api_client.models import PaginatedDocumentList


@dataclass
class DocumentBrowseViewModel:
    documents: list[dict[str, Any]] = field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 1


def build_document_browse_view_model(page: PaginatedDocumentList) -> DocumentBrowseViewModel:
    return DocumentBrowseViewModel(
        documents=[item.model_dump() for item in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
        total_pages=page.total_pages,
    )


def load_document_statistics(client: PlatformApiClient) -> dict[str, Any]:
    stats = client.documents.get_statistics()
    return stats.model_dump()

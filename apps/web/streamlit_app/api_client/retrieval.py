from __future__ import annotations

from typing import Optional

from apps.web.streamlit_app.api_client.base import BaseApiClient
from apps.web.streamlit_app.api_client.models import ContextPreviewResponse, SearchRequest, SearchResponse


class RetrievalApiClient:
    def __init__(self, client: BaseApiClient) -> None:
        self._client = client

    def search(
        self,
        *,
        query: str,
        mode: str = "hybrid",
        top_k: int = 5,
        filters: Optional[dict] = None,
    ) -> SearchResponse:
        payload = SearchRequest(
            query=query,
            mode=mode,
            top_k=top_k,
            filters=filters or {},
        )
        data = self._client.post_json("/v1/retrieval/search", json=payload.model_dump())
        return SearchResponse.model_validate(data)

    def context_preview(
        self,
        *,
        query: str,
        mode: str = "hybrid",
        top_k: int = 5,
        filters: Optional[dict] = None,
    ) -> ContextPreviewResponse:
        payload = SearchRequest(
            query=query,
            mode=mode,
            top_k=top_k,
            filters=filters or {},
        )
        data = self._client.post_json("/v1/retrieval/context-preview", json=payload.model_dump())
        return ContextPreviewResponse.model_validate(data)

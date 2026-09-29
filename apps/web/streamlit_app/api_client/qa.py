from __future__ import annotations

from typing import Optional

from apps.web.streamlit_app.api_client.base import BaseApiClient
from apps.web.streamlit_app.api_client.models import QuestionAnswerResponse, SearchRequest


class QuestionAnsweringApiClient:
    def __init__(self, client: BaseApiClient) -> None:
        self._client = client

    def ask(
        self,
        *,
        query: str,
        mode: str = "hybrid",
        top_k: int = 5,
        filters: Optional[dict] = None,
    ) -> QuestionAnswerResponse:
        payload = SearchRequest(query=query, mode=mode, top_k=top_k, filters=filters or {})
        data = self._client.post_json("/v1/qa/ask", json=payload.model_dump())
        return QuestionAnswerResponse.model_validate(data)

    def ask_document(
        self,
        document_id: str,
        *,
        query: str,
        mode: str = "hybrid",
        top_k: int = 5,
        filters: Optional[dict] = None,
    ) -> QuestionAnswerResponse:
        payload = SearchRequest(query=query, mode=mode, top_k=top_k, filters=filters or {})
        data = self._client.post_json(f"/v1/qa/ask/document/{document_id}", json=payload.model_dump())
        return QuestionAnswerResponse.model_validate(data)

    def ask_documents(
        self,
        document_ids: list[str],
        *,
        query: str,
        mode: str = "hybrid",
        top_k: int = 5,
        filters: Optional[dict] = None,
    ) -> QuestionAnswerResponse:
        payload = SearchRequest(query=query, mode=mode, top_k=top_k, filters=filters or {}).model_dump()
        payload["document_ids"] = document_ids
        data = self._client.post_json("/v1/qa/ask/documents", json=payload)
        return QuestionAnswerResponse.model_validate(data)

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_API_BASE_URL = "http://localhost:8000"


class ApiClientError(Exception):
    def __init__(
        self, message: str, *, code: str | None = None, status_code: int | None = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class ApiClient:
    """Thin HTTP wrapper around the FastAPI backend used by the Streamlit frontend."""

    def __init__(self, base_url: str | None = None, *, timeout_seconds: float = 120.0) -> None:
        self.base_url = (base_url or os.getenv("API_BASE_URL") or DEFAULT_API_BASE_URL).rstrip("/")
        self._timeout = timeout_seconds

    def liveness(self) -> dict[str, Any]:
        return self._request("GET", "/v1/health/live")

    def readiness(self) -> dict[str, Any]:
        # The readiness endpoint returns 503 when a dependency is down.
        return self._request("GET", "/v1/health/ready", accept_statuses={503})

    def knowledge_base_stats(self) -> dict[str, Any]:
        return self._request("GET", "/v1/documents/stats")

    def list_documents(self, *, page: int = 1, page_size: int = 50) -> dict[str, Any]:
        return self._request("GET", "/v1/documents", params={"page": page, "page_size": page_size})

    def upload_document(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: str | None,
        company: str | None = None,
        document_type: str | None = None,
        tags: str | None = None,
    ) -> dict[str, Any]:
        form = {
            key: value
            for key, value in {
                "company": company,
                "document_type": document_type,
                "tags": tags,
            }.items()
            if value
        }
        files = {"file": (filename, content, content_type or "application/octet-stream")}
        return self._request("POST", "/v1/documents", data=form, files=files)

    def index_document(self, document_id: str) -> dict[str, Any]:
        return self._request("POST", f"/v1/documents/{document_id}/index")

    def ask_question(self, *, query: str, mode: str = "hybrid", top_k: int = 5) -> dict[str, Any]:
        return self._request(
            "POST", "/v1/qa/ask", json={"query": query, "mode": mode, "top_k": top_k}
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        accept_statuses: set[int] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        try:
            with httpx.Client(base_url=self.base_url, timeout=self._timeout) as client:
                response = client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise ApiClientError(f"Cannot reach the API at {self.base_url}: {exc}") from exc

        if response.is_success or response.status_code in (accept_statuses or set()):
            return response.json() if response.content else {}

        try:
            payload = response.json()
        except ValueError:
            payload = {}
        raise ApiClientError(
            payload.get("message") or f"API request failed with status {response.status_code}.",
            code=payload.get("code"),
            status_code=response.status_code,
        )

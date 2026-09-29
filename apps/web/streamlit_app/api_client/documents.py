from __future__ import annotations

from typing import Any, Optional

from apps.web.streamlit_app.api_client.base import BaseApiClient
from apps.web.streamlit_app.api_client.models import (
    DocumentChunk,
    DocumentChunkList,
    DocumentDetail,
    DocumentIndexingStatus,
    DocumentIndexingVisibility,
    KnowledgeBaseStatistics,
    PaginatedDocumentList,
)


class DocumentsApiClient:
    def __init__(self, client: BaseApiClient) -> None:
        self._client = client

    def list_documents(
        self,
        *,
        search: Optional[str] = None,
        company: Optional[str] = None,
        document_type: Optional[str] = None,
        source: Optional[str] = None,
        indexing_status: Optional[str] = None,
        tags: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_direction: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedDocumentList:
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if search:
            params["search"] = search
        if company:
            params["company"] = company
        if document_type:
            params["document_type"] = document_type
        if source:
            params["source"] = source
        if indexing_status:
            params["indexing_status"] = indexing_status
        if tags:
            params["tags"] = tags
        if sort_by:
            params["sort_by"] = sort_by
        if sort_direction:
            params["sort_direction"] = sort_direction
        data = self._client.get_json("/v1/documents", params=params)
        return PaginatedDocumentList.model_validate(data)

    def get_statistics(self) -> KnowledgeBaseStatistics:
        data = self._client.get_json("/v1/documents/stats")
        return KnowledgeBaseStatistics.model_validate(data)

    def get_document(self, document_id: str) -> DocumentDetail:
        data = self._client.get_json(f"/v1/documents/{document_id}")
        return DocumentDetail.model_validate(data)

    def upload_document(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[dict[str, str]] = None,
        chunking: Optional[dict[str, Any]] = None,
    ) -> DocumentDetail:
        data: dict[str, Any] = {}
        if chunking:
            data.update(chunking)
        if metadata:
            data.update(metadata)
        payload = self._client.post_multipart(
            "/v1/documents",
            data=data,
            files={"file": (filename, content, content_type)},
        )
        return DocumentDetail.model_validate(payload)

    def delete_document(self, document_id: str) -> None:
        self._client.delete(f"/v1/documents/{document_id}")

    def index_document(self, document_id: str) -> DocumentIndexingStatus:
        data = self._client.post_json(f"/v1/documents/{document_id}/index")
        return DocumentIndexingStatus.model_validate(data)

    def reindex_document(self, document_id: str) -> DocumentIndexingStatus:
        data = self._client.post_json(f"/v1/documents/{document_id}/reindex")
        return DocumentIndexingStatus.model_validate(data)

    def list_chunks(
        self,
        document_id: str,
        *,
        page_number: Optional[int] = None,
        tags: Optional[str] = None,
        embedding_status: Optional[str] = None,
    ) -> DocumentChunkList:
        params: dict[str, Any] = {}
        if page_number is not None:
            params["page_number"] = page_number
        if tags:
            params["tags"] = tags
        if embedding_status:
            params["embedding_status"] = embedding_status
        data = self._client.get_json(f"/v1/documents/{document_id}/chunks", params=params)
        return DocumentChunkList.model_validate(data)

    def get_chunk(self, document_id: str, chunk_id: str) -> DocumentChunk:
        data = self._client.get_json(f"/v1/documents/{document_id}/chunks/{chunk_id}")
        return DocumentChunk.model_validate(data)

    def get_indexing_status(self, document_id: str) -> DocumentIndexingStatus:
        data = self._client.get_json(f"/v1/documents/{document_id}/indexing-status")
        return DocumentIndexingStatus.model_validate(data)

    def get_indexing_visibility(self, document_id: str) -> DocumentIndexingVisibility:
        data = self._client.get_json(f"/v1/documents/{document_id}/indexing-visibility")
        return DocumentIndexingVisibility.model_validate(data)

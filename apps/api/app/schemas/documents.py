from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class DocumentSummaryResponse(BaseModel):
    document_id: str
    filename: str
    extension: str
    mime_type: str
    checksum_sha256: str
    size_bytes: int
    title: Optional[str]
    company: Optional[str]
    document_type: Optional[str]
    source: Optional[str]
    document_date: Optional[str]
    tags: list[str]
    source_format: str
    chunk_count: int
    indexing_status: str
    indexing_error: Optional[str]
    embedding_provider: Optional[str]
    embedding_model: Optional[str]
    embedding_dimensions: Optional[int]
    indexed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class PaginatedDocumentListResponse(BaseModel):
    items: list[DocumentSummaryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class DocumentDetailResponse(DocumentSummaryResponse):
    raw_char_count: int
    normalized_char_count: int
    word_count: int
    normalized_text: str
    attributes: dict[str, Any]
    embedding_count: int
    last_indexed_at: Optional[datetime]


class DocumentChunkResponse(BaseModel):
    chunk_id: str
    document_id: str
    index: int
    page_number: Optional[int]
    tags: list[str]
    text: str
    strategy: str
    start_offset: int
    end_offset: int
    metadata: dict[str, Any]
    embedding_status: str
    embedding_provider: Optional[str]
    embedding_model: Optional[str]
    embedding_dimensions: Optional[int]
    embedding_token_count: Optional[int]
    embedding_cost_usd: Optional[float]
    has_embedding: bool
    embedded_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class DocumentChunkListResponse(BaseModel):
    document_id: str
    total: int
    page_number: Optional[int]
    tags: list[str]
    embedding_status: Optional[str]
    chunks: list[DocumentChunkResponse]


class DocumentIndexingStatusResponse(BaseModel):
    document_id: str
    indexing_status: str
    indexing_error: Optional[str]
    embedding_provider: Optional[str]
    embedding_model: Optional[str]
    embedding_dimensions: Optional[int]
    indexed_at: Optional[datetime]
    last_indexed_at: Optional[datetime]
    chunk_count: int
    embedding_count: int
    updated_at: datetime


class DocumentIndexingHistoryEntryResponse(BaseModel):
    status: str
    timestamp: datetime
    error: Optional[str]


class DocumentIndexingVisibilityResponse(BaseModel):
    document_id: str
    indexing_status: str
    indexing_error: Optional[str]
    chunk_count: int
    embedding_count: int
    failed_chunk_count: int
    failed_chunks: list[DocumentChunkResponse]
    retry_eligible: bool
    history_available: bool
    indexing_history: list[DocumentIndexingHistoryEntryResponse]
    last_indexed_at: Optional[datetime]
    updated_at: datetime


class KnowledgeBaseStatisticsResponse(BaseModel):
    total_documents: int
    total_chunks: int
    indexed_chunks: int
    failed_chunks: int
    documents_by_type: dict[str, int]
    documents_by_company: dict[str, int]
    average_chunks_per_document: float

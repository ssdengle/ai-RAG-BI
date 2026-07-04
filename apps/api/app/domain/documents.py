from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


ChunkingStrategyName = Literal["recursive", "semantic", "sliding_window"]
DocumentSortBy = Literal["created_at", "title", "company", "document_type", "indexing_status"]
SortDirection = Literal["asc", "desc"]
ChunkEmbeddingStatus = Literal["embedded", "missing"]


class IndexingStatus(str, Enum):
    PENDING = "pending"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"


@dataclass(frozen=True)
class ParsedDocument:
    text: str
    title: str | None = None
    extracted_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChunkingOptions:
    strategy: ChunkingStrategyName = "recursive"
    max_chunk_size: int = 800
    overlap_size: int = 100
    window_size: int = 120
    step_size: int = 80


@dataclass(frozen=True)
class DocumentMetadata:
    document_id: str
    filename: str
    extension: str
    mime_type: str
    checksum_sha256: str
    size_bytes: int
    title: str | None
    raw_char_count: int
    normalized_char_count: int
    word_count: int
    source_format: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    document_id: str
    index: int
    text: str
    strategy: ChunkingStrategyName
    start_offset: int
    end_offset: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IngestedDocument:
    metadata: DocumentMetadata
    normalized_text: str
    chunks: list[DocumentChunk]


@dataclass(frozen=True)
class PersistedDocument:
    document_id: str
    filename: str
    extension: str
    mime_type: str
    checksum_sha256: str
    size_bytes: int
    title: str | None
    raw_char_count: int
    normalized_char_count: int
    word_count: int
    source_format: str
    normalized_text: str
    attributes: dict[str, Any]
    chunk_count: int
    indexing_status: IndexingStatus
    indexing_error: str | None
    embedding_provider: str | None
    embedding_model: str | None
    embedding_dimensions: int | None
    indexed_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class PersistedDocumentChunk:
    chunk_id: str
    document_id: str
    index: int
    text: str
    strategy: ChunkingStrategyName
    start_offset: int
    end_offset: int
    metadata: dict[str, Any]
    embedding_provider: str | None
    embedding_model: str | None
    embedding_dimensions: int | None
    embedding_token_count: int | None
    embedding_cost_usd: float | None
    embedding_vector: list[float] | None
    embedded_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class DocumentBrowseFilters:
    company: str | None = None
    document_type: str | None = None
    source: str | None = None
    indexing_status: IndexingStatus | None = None
    search: str | None = None
    tags: list[str] | None = None


@dataclass(frozen=True)
class DocumentBrowseQuery:
    filters: DocumentBrowseFilters = field(default_factory=DocumentBrowseFilters)
    sort_by: DocumentSortBy = "created_at"
    sort_direction: SortDirection = "desc"
    page: int = 1
    page_size: int = 20


@dataclass(frozen=True)
class DocumentBrowsePage:
    items: list[PersistedDocument]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True)
class ChunkExplorerFilters:
    page_number: int | None = None
    tags: list[str] | None = None
    embedding_status: ChunkEmbeddingStatus | None = None


@dataclass(frozen=True)
class DocumentDetailView:
    document: PersistedDocument
    embedding_count: int
    last_indexed_at: datetime | None


@dataclass(frozen=True)
class ChunkExplorerView:
    document: PersistedDocument
    chunks: list[PersistedDocumentChunk]
    total: int
    filters: ChunkExplorerFilters = field(default_factory=ChunkExplorerFilters)


@dataclass(frozen=True)
class IndexingHistoryEntry:
    status: IndexingStatus
    timestamp: datetime
    error: str | None = None


@dataclass(frozen=True)
class IndexingVisibilityView:
    document: PersistedDocument
    embedding_count: int
    failed_chunks: list[PersistedDocumentChunk]
    indexing_history: list[IndexingHistoryEntry] = field(default_factory=list)
    history_available: bool = False
    retry_eligible: bool = False


@dataclass(frozen=True)
class KnowledgeBaseStatistics:
    total_documents: int
    total_chunks: int
    indexed_chunks: int
    failed_chunks: int
    documents_by_type: dict[str, int]
    documents_by_company: dict[str, int]
    average_chunks_per_document: float

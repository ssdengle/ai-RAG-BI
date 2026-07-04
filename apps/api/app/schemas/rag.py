from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


ChunkingStrategyValue = Literal["recursive", "semantic", "sliding_window"]


class IngestionPreviewRequest(BaseModel):
    filename: str = Field(..., min_length=1)
    content_type: Optional[str] = None
    content: str = Field(..., min_length=1, description="UTF-8 text payload for preview ingestion.")
    strategy: ChunkingStrategyValue = "recursive"
    max_chunk_size: int = Field(default=800, ge=50, le=4000)
    overlap_size: int = Field(default=100, ge=0, le=1000)
    window_size: int = Field(default=120, ge=20, le=1000)
    step_size: int = Field(default=80, ge=10, le=1000)


class ChunkResponse(BaseModel):
    chunk_id: str
    index: int
    strategy: ChunkingStrategyValue
    text: str
    start_offset: int
    end_offset: int
    metadata: dict[str, Any]


class DocumentMetadataResponse(BaseModel):
    document_id: str
    filename: str
    extension: str
    mime_type: str
    checksum_sha256: str
    size_bytes: int
    title: Optional[str]
    raw_char_count: int
    normalized_char_count: int
    word_count: int
    source_format: str
    attributes: dict[str, Any]


class IngestionPreviewResponse(BaseModel):
    metadata: DocumentMetadataResponse
    normalized_text: str
    chunk_count: int
    chunks: list[ChunkResponse]

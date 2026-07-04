from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class RetrievalFiltersRequest(BaseModel):
    document_ids: Optional[list[str]] = None
    company: Optional[str] = None
    document_type: Optional[str] = None
    source: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    tags: Optional[list[str]] = None


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    mode: Literal["semantic", "keyword", "hybrid"] = "hybrid"
    top_k: int = Field(default=5, ge=1, le=20)
    filters: RetrievalFiltersRequest = Field(default_factory=RetrievalFiltersRequest)


class AskQuestionRequest(SearchRequest):
    pass


class AskQuestionAcrossDocumentsRequest(SearchRequest):
    document_ids: list[str] = Field(..., min_length=1)


class CitationResponse(BaseModel):
    document_id: str
    title: Optional[str]
    chunk_id: str
    page_number: Optional[int]
    score: float
    snippet: str


class RetrievedChunkResponse(BaseModel):
    chunk_id: str
    document_id: str
    document_title: Optional[str]
    text: str
    score: float
    semantic_score: Optional[float]
    keyword_score: Optional[float]
    rerank_score: Optional[float]
    page_number: Optional[int]
    document_metadata: dict[str, Any]
    chunk_metadata: dict[str, Any]


class SearchResponse(BaseModel):
    mode: str
    query: str
    total_candidates: int
    chunks: list[RetrievedChunkResponse]
    citations: list[CitationResponse]


class ContextPreviewResponse(BaseModel):
    mode: str
    query: str
    context: str
    chunk_count: int
    truncated: bool
    citations: list[CitationResponse]


class QuestionAnswerResponse(BaseModel):
    answer: str
    confidence: float
    llm_provider: Optional[str]
    llm_model: Optional[str]
    finish_reason: Optional[str]
    retrieval: SearchResponse
    citations: list[CitationResponse]
    context_preview: str

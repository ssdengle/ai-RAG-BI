from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional


RetrievalMode = Literal["semantic", "keyword", "hybrid"]


@dataclass(frozen=True)
class RetrievalFilters:
    document_ids: Optional[list[str]] = None
    company: Optional[str] = None
    document_type: Optional[str] = None
    source: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    tags: Optional[list[str]] = None


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    document_id: str
    document_title: Optional[str]
    text: str
    score: float
    semantic_score: Optional[float] = None
    keyword_score: Optional[float] = None
    rerank_score: Optional[float] = None
    page_number: Optional[int] = None
    document_metadata: dict[str, Any] = field(default_factory=dict)
    chunk_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Citation:
    document_id: str
    title: Optional[str]
    chunk_id: str
    page_number: Optional[int]
    score: float
    snippet: str


@dataclass(frozen=True)
class AssembledContext:
    text: str
    citations: list[Citation]
    chunk_count: int
    truncated: bool


@dataclass(frozen=True)
class RetrievalResult:
    mode: RetrievalMode
    query: str
    chunks: list[RetrievedChunk]
    citations: list[Citation]
    total_candidates: int


@dataclass(frozen=True)
class QuestionAnswerResult:
    answer: str
    citations: list[Citation]
    confidence: float
    retrieval: RetrievalResult
    context: AssembledContext
    llm_provider: Optional[str]
    llm_model: Optional[str]
    finish_reason: Optional[str]

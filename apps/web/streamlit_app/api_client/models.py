from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class CitationModel(BaseModel):
    document_id: str
    title: Optional[str] = None
    chunk_id: str
    page_number: Optional[int] = None
    score: float = 0.0
    snippet: str = ""


class RetrievalFilters(BaseModel):
    document_ids: Optional[list[str]] = None
    company: Optional[str] = None
    document_type: Optional[str] = None
    source: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    tags: Optional[list[str]] = None


class SearchRequest(BaseModel):
    query: str
    mode: str = "hybrid"
    top_k: int = 5
    filters: RetrievalFilters = Field(default_factory=RetrievalFilters)


class RetrievedChunkModel(BaseModel):
    chunk_id: str
    document_id: str
    document_title: Optional[str] = None
    text: str
    score: float
    document_metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    mode: str
    query: str
    total_candidates: int
    chunks: list[RetrievedChunkModel]
    citations: list[CitationModel]


class ContextPreviewResponse(BaseModel):
    mode: str
    query: str
    context: str
    chunk_count: int
    truncated: bool
    citations: list[CitationModel]


class QuestionAnswerResponse(BaseModel):
    answer: str
    confidence: float
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    finish_reason: Optional[str] = None
    retrieval: SearchResponse
    citations: list[CitationModel]
    context_preview: Optional[str] = None


class DocumentSummary(BaseModel):
    document_id: str
    filename: str
    extension: str
    mime_type: str
    checksum_sha256: str
    size_bytes: int
    title: Optional[str] = None
    company: Optional[str] = None
    document_type: Optional[str] = None
    source: Optional[str] = None
    document_date: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    source_format: str
    chunk_count: int
    indexing_status: str
    indexing_error: Optional[str] = None
    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None
    embedding_dimensions: Optional[int] = None
    indexed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class PaginatedDocumentList(BaseModel):
    items: list[DocumentSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class DocumentDetail(DocumentSummary):
    raw_char_count: int
    normalized_char_count: int
    word_count: int
    normalized_text: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    embedding_count: int
    last_indexed_at: Optional[datetime] = None


class DocumentChunk(BaseModel):
    chunk_id: str
    document_id: str
    index: int
    page_number: Optional[int] = None
    tags: list[str] = Field(default_factory=list)
    text: str
    strategy: str
    start_offset: int
    end_offset: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding_status: str
    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None
    embedding_dimensions: Optional[int] = None
    embedding_token_count: Optional[int] = None
    embedding_cost_usd: Optional[float] = None
    has_embedding: bool
    embedded_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class DocumentChunkList(BaseModel):
    document_id: str
    total: int
    page_number: Optional[int] = None
    tags: list[str] = Field(default_factory=list)
    embedding_status: Optional[str] = None
    chunks: list[DocumentChunk]


class DocumentIndexingStatus(BaseModel):
    document_id: str
    indexing_status: str
    indexing_error: Optional[str] = None
    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None
    embedding_dimensions: Optional[int] = None
    indexed_at: Optional[datetime] = None
    last_indexed_at: Optional[datetime] = None
    chunk_count: int
    embedding_count: int
    updated_at: datetime


class IndexingHistoryEntry(BaseModel):
    status: str
    timestamp: datetime
    error: Optional[str] = None


class DocumentIndexingVisibility(BaseModel):
    document_id: str
    indexing_status: str
    indexing_error: Optional[str] = None
    chunk_count: int
    embedding_count: int
    failed_chunk_count: int
    failed_chunks: list[DocumentChunk] = Field(default_factory=list)
    retry_eligible: bool
    history_available: bool
    indexing_history: list[IndexingHistoryEntry] = Field(default_factory=list)
    last_indexed_at: Optional[datetime] = None
    updated_at: datetime


class KnowledgeBaseStatistics(BaseModel):
    total_documents: int
    total_chunks: int
    indexed_chunks: int
    failed_chunks: int
    documents_by_type: dict[str, int] = Field(default_factory=dict)
    documents_by_company: dict[str, int] = Field(default_factory=dict)
    average_chunks_per_document: float


class CompanyProfile(BaseModel):
    company_id: str
    name: str
    display_name: str
    industry: Optional[str] = None
    description: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class CompanyProfileDetail(CompanyProfile):
    document_count: int
    documents_by_type: dict[str, int] = Field(default_factory=dict)
    total_chunks: int
    indexed_document_count: int


class CompetitorRelationship(BaseModel):
    relationship_id: str
    company_id: str
    competitor_company_id: str
    competitor_name: str
    relationship_type: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime


class CompanyComparisonMetric(BaseModel):
    company_id: str
    company_name: str
    document_count: int
    total_chunks: int
    indexed_document_count: int
    top_document_types: dict[str, int] = Field(default_factory=dict)
    evidence_snippets: list[str] = Field(default_factory=list)


class CompanyComparison(BaseModel):
    companies: list[CompanyComparisonMetric]
    comparison_query: str
    shared_topics: list[str] = Field(default_factory=list)
    citations: list[CitationModel] = Field(default_factory=list)


class RiskCategorySummary(BaseModel):
    category: str
    count: int
    top_snippets: list[str] = Field(default_factory=list)
    average_score: float = 0.0


class RiskSummary(BaseModel):
    company_id: str
    company_name: str
    total_evidence_count: int
    categories: list[RiskCategorySummary] = Field(default_factory=list)
    citations: list[CitationModel] = Field(default_factory=list)
    evidence_available: bool


class RiskComparison(BaseModel):
    companies: list[RiskSummary]
    shared_categories: list[str] = Field(default_factory=list)
    unique_categories_by_company: dict[str, list[str]] = Field(default_factory=dict)


class TrendTopicSummary(BaseModel):
    topic: str
    count: int
    document_types: dict[str, int] = Field(default_factory=dict)
    top_snippets: list[str] = Field(default_factory=list)
    average_score: float = 0.0


class TrendSummary(BaseModel):
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    document_type: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    total_evidence_count: int
    topics: list[TrendTopicSummary] = Field(default_factory=list)
    citations: list[CitationModel] = Field(default_factory=list)
    evidence_available: bool


class ExecutiveBrief(BaseModel):
    title: str
    summary: str
    key_points: list[str] = Field(default_factory=list)
    citations: list[CitationModel] = Field(default_factory=list)
    confidence: float
    human_review_recommended: bool
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    topic: Optional[str] = None


class WorkflowResponse(BaseModel):
    workflow_id: str
    status: str
    user_request: str
    company_id: Optional[str] = None
    company_ids: list[str] = Field(default_factory=list)
    topic: str
    plan: list[str] = Field(default_factory=list)
    completed_steps: list[str] = Field(default_factory=list)
    failed_steps: list[str] = Field(default_factory=list)
    confidence: Optional[float] = None
    human_review_required: bool = False
    retry_count: int = 0
    max_retries: int = 2
    final_output: Optional[dict[str, Any]] = None
    errors: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class WorkflowStateResponse(BaseModel):
    workflow_id: str
    status: str
    state: dict[str, Any] = Field(default_factory=dict)


class WorkflowTraceEvent(BaseModel):
    agent: str
    event_type: str
    message: str
    timestamp: str
    confidence: Optional[float] = None
    tool_calls: list[Any] = Field(default_factory=list)
    latency_ms: Optional[float] = None
    retrieval_statistics: Optional[dict[str, Any]] = None


class WorkflowTraceResponse(BaseModel):
    workflow_id: str
    trace: list[WorkflowTraceEvent] = Field(default_factory=list)


class BenchmarkDataset(BaseModel):
    dataset_id: str
    name: str
    description: str
    target_type: str
    version: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ExpectedAnswer(BaseModel):
    text: str
    required_citations: list[str] = Field(default_factory=list)
    required_keywords: list[str] = Field(default_factory=list)
    min_confidence: Optional[float] = None


class TestCase(BaseModel):
    test_case_id: str
    dataset_id: str
    name: str
    query: str
    expected_answer: ExpectedAnswer
    source_documents: list[dict[str, Any]] = Field(default_factory=list)
    rubric: dict[str, Any] = Field(default_factory=dict)
    input_payload: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class EvaluationRun(BaseModel):
    run_id: str
    dataset_id: str
    status: str
    target_type: str
    config: dict[str, Any] = Field(default_factory=dict)
    baseline_run_id: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    summary: dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ScorerResult(BaseModel):
    scorer: str
    score: float
    passed: bool
    details: dict[str, Any] = Field(default_factory=dict)


class EvaluationResult(BaseModel):
    result_id: str
    run_id: str
    test_case_id: str
    test_case_name: str
    passed: bool
    overall_score: float
    scorer_results: list[ScorerResult] = Field(default_factory=list)
    failure_modes: list[str] = Field(default_factory=list)
    actual_output: dict[str, Any] = Field(default_factory=dict)
    latency_ms: Optional[float] = None
    token_usage: dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    created_at: datetime


class EvaluationReport(BaseModel):
    run_id: str
    dataset_id: str
    dataset_name: str
    target_type: str
    status: str
    passed: bool
    average_score: float
    pass_rate: float
    total_test_cases: int
    passed_test_cases: int
    failed_test_cases: list[dict[str, Any]] = Field(default_factory=list)
    failure_mode_summary: dict[str, int] = Field(default_factory=dict)
    model_comparison: dict[str, Any] = Field(default_factory=dict)
    regression_comparison: dict[str, Any] = Field(default_factory=dict)
    scorer_averages: dict[str, float] = Field(default_factory=dict)
    created_at: datetime
    completed_at: Optional[datetime] = None


class HealthLiveResponse(BaseModel):
    status: str
    service: str
    environment: str


class HealthReadyResponse(BaseModel):
    status: str
    checks: dict[str, Any] = Field(default_factory=dict)

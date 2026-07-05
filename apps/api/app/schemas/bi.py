from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from apps.api.app.schemas.retrieval import CitationResponse


class CreateCompanyProfileRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    display_name: str = Field(..., min_length=1, max_length=255)
    industry: Optional[str] = None
    description: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CompanyProfileResponse(BaseModel):
    company_id: str
    name: str
    display_name: str
    industry: Optional[str]
    description: Optional[str]
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class CompanyDocumentSummaryResponse(BaseModel):
    document_id: str
    title: Optional[str]
    document_type: Optional[str]
    source: Optional[str]
    document_date: Optional[str]
    indexing_status: str
    chunk_count: int


class CompanyProfileDetailResponse(CompanyProfileResponse):
    document_count: int
    documents_by_type: dict[str, int]
    total_chunks: int
    indexed_document_count: int
    documents: list[CompanyDocumentSummaryResponse]


class AddCompetitorRequest(BaseModel):
    competitor_company_id: str
    relationship_type: Optional[str] = None
    notes: Optional[str] = None


class CompetitorRelationshipResponse(BaseModel):
    relationship_id: str
    company_id: str
    competitor_company_id: str
    competitor_name: str
    relationship_type: Optional[str]
    notes: Optional[str]
    created_at: datetime


class CompareCompaniesRequest(BaseModel):
    company_ids: list[str] = Field(..., min_length=2)
    query: str = Field(..., min_length=1)
    mode: Literal["semantic", "keyword", "hybrid"] = "hybrid"
    top_k: int = Field(default=5, ge=1, le=20)


class CompanyComparisonMetricResponse(BaseModel):
    company_id: str
    company_name: str
    document_count: int
    total_chunks: int
    indexed_document_count: int
    top_document_types: dict[str, int]
    evidence_snippets: list[str]


class CompanyComparisonResponse(BaseModel):
    companies: list[CompanyComparisonMetricResponse]
    comparison_query: str
    shared_topics: list[str]
    citations: list[CitationResponse]


class RiskSummaryRequest(BaseModel):
    refresh: bool = False
    mode: Literal["semantic", "keyword", "hybrid"] = "hybrid"
    top_k: int = Field(default=8, ge=1, le=20)


class CompareRisksRequest(BaseModel):
    company_ids: list[str] = Field(..., min_length=2)
    refresh: bool = False
    mode: Literal["semantic", "keyword", "hybrid"] = "hybrid"
    top_k: int = Field(default=8, ge=1, le=20)


class RiskCategorySummaryResponse(BaseModel):
    category: str
    count: int
    top_snippets: list[str]
    average_score: float


class RiskSummaryResponse(BaseModel):
    company_id: str
    company_name: str
    total_evidence_count: int
    categories: list[RiskCategorySummaryResponse]
    citations: list[CitationResponse]
    evidence_available: bool


class RiskComparisonResponse(BaseModel):
    companies: list[RiskSummaryResponse]
    shared_categories: list[str]
    unique_categories_by_company: dict[str, list[str]]


class TrendSummaryRequest(BaseModel):
    company_id: Optional[str] = None
    document_type: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    refresh: bool = False
    mode: Literal["semantic", "keyword", "hybrid"] = "hybrid"
    top_k: int = Field(default=8, ge=1, le=20)


class TrendTopicSummaryResponse(BaseModel):
    topic: str
    count: int
    document_types: dict[str, int]
    top_snippets: list[str]
    average_score: float


class TrendSummaryResponse(BaseModel):
    company_id: Optional[str]
    company_name: Optional[str]
    document_type: Optional[str]
    date_from: Optional[str]
    date_to: Optional[str]
    total_evidence_count: int
    topics: list[TrendTopicSummaryResponse]
    citations: list[CitationResponse]
    evidence_available: bool


class ExecutiveBriefRequest(BaseModel):
    topic: str = Field(..., min_length=1)
    company_id: Optional[str] = None
    mode: Literal["semantic", "keyword", "hybrid"] = "hybrid"
    top_k: int = Field(default=6, ge=1, le=20)


class ExecutiveBriefResponse(BaseModel):
    title: str
    summary: str
    key_points: list[str]
    citations: list[CitationResponse]
    confidence: float
    human_review_recommended: bool
    llm_provider: Optional[str]
    llm_model: Optional[str]
    company_id: Optional[str]
    company_name: Optional[str]
    topic: str

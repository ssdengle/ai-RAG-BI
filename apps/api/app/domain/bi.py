from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from apps.api.app.domain.retrieval import Citation


@dataclass(frozen=True)
class CompanyProfile:
    company_id: str
    name: str
    display_name: str
    industry: Optional[str]
    description: Optional[str]
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class CompanyDocumentSummary:
    document_id: str
    title: Optional[str]
    document_type: Optional[str]
    source: Optional[str]
    document_date: Optional[str]
    indexing_status: str
    chunk_count: int


@dataclass(frozen=True)
class CompanyProfileDetail:
    profile: CompanyProfile
    document_count: int
    documents_by_type: dict[str, int]
    total_chunks: int
    indexed_document_count: int
    documents: list[CompanyDocumentSummary]


@dataclass(frozen=True)
class CompetitorRelationship:
    relationship_id: str
    company_id: str
    competitor_company_id: str
    competitor_name: str
    relationship_type: Optional[str]
    notes: Optional[str]
    created_at: datetime


@dataclass(frozen=True)
class CompanyComparisonMetric:
    company_id: str
    company_name: str
    document_count: int
    total_chunks: int
    indexed_document_count: int
    top_document_types: dict[str, int]
    evidence_snippets: list[str]


@dataclass(frozen=True)
class CompanyComparisonResult:
    companies: list[CompanyComparisonMetric]
    comparison_query: str
    shared_topics: list[str]
    citations: list[Citation]


@dataclass(frozen=True)
class RiskEvidence:
    evidence_id: str
    company_id: str
    document_id: str
    chunk_id: str
    risk_category: str
    summary_text: str
    snippet: str
    score: float
    extracted_at: datetime


@dataclass(frozen=True)
class RiskCategorySummary:
    category: str
    count: int
    top_snippets: list[str]
    average_score: float


@dataclass(frozen=True)
class RiskSummary:
    company_id: str
    company_name: str
    total_evidence_count: int
    categories: list[RiskCategorySummary]
    citations: list[Citation]
    evidence_available: bool


@dataclass(frozen=True)
class RiskComparisonResult:
    companies: list[RiskSummary]
    shared_categories: list[str]
    unique_categories_by_company: dict[str, list[str]]


@dataclass(frozen=True)
class TrendEvidence:
    evidence_id: str
    company_id: str
    document_id: str
    chunk_id: str
    trend_topic: str
    document_type: Optional[str]
    document_date: Optional[str]
    summary_text: str
    snippet: str
    score: float
    extracted_at: datetime


@dataclass(frozen=True)
class TrendTopicSummary:
    topic: str
    count: int
    document_types: dict[str, int]
    top_snippets: list[str]
    average_score: float


@dataclass(frozen=True)
class TrendSummary:
    company_id: Optional[str]
    company_name: Optional[str]
    document_type: Optional[str]
    date_from: Optional[str]
    date_to: Optional[str]
    total_evidence_count: int
    topics: list[TrendTopicSummary]
    citations: list[Citation]
    evidence_available: bool


@dataclass(frozen=True)
class ExecutiveBrief:
    title: str
    summary: str
    key_points: list[str]
    citations: list[Citation]
    confidence: float
    human_review_recommended: bool
    llm_provider: Optional[str]
    llm_model: Optional[str]
    company_id: Optional[str]
    company_name: Optional[str]
    topic: str

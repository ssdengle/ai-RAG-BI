from __future__ import annotations

from datetime import datetime, timezone

from apps.api.app.domain.bi import CompanyProfile, CompanyProfileDetail, RiskEvidence
from apps.api.app.domain.retrieval import Citation, RetrievedChunk
from apps.api.app.services.evidence_classifier import (
    classify_risk_categories,
    classify_trend_topics,
    summarize_chunk_text,
)
from apps.api.app.services.executive_brief_service import (
    ExecutiveBriefService,
    _requires_human_review,
)
from apps.api.app.services.risk_tracking_service import _build_risk_evidence, _build_risk_summary


def test_classify_risk_categories_detects_regulatory_and_financial_terms() -> None:
    categories = classify_risk_categories(
        "The company faces regulatory compliance risk and liquidity pressure."
    )

    assert "regulatory" in categories
    assert "financial" in categories


def test_classify_trend_topics_detects_revenue_growth() -> None:
    topics = classify_trend_topics("Revenue increased steadily across all regions.")

    assert "revenue_growth" in topics


def test_build_risk_evidence_from_retrieved_chunks() -> None:
    chunks = [
        RetrievedChunk(
            chunk_id="chunk-1",
            document_id="doc-1",
            document_title="10-K",
            text="Cyber security incidents could disrupt operations.",
            score=0.88,
        )
    ]

    evidence = _build_risk_evidence("company-1", chunks)

    assert len(evidence) >= 1
    assert evidence[0].company_id == "company-1"
    assert evidence[0].risk_category in {"technology", "operational", "general"}


def test_build_risk_summary_groups_categories_and_preserves_citations() -> None:
    now = datetime.now(timezone.utc)
    evidence = [
        RiskEvidence(
            evidence_id="risk-1",
            company_id="company-1",
            document_id="doc-1",
            chunk_id="chunk-1",
            risk_category="financial",
            summary_text="Financial risk indicated.",
            snippet="Liquidity pressure remains elevated.",
            score=0.9,
            extracted_at=now,
        ),
        RiskEvidence(
            evidence_id="risk-2",
            company_id="company-1",
            document_id="doc-2",
            chunk_id="chunk-2",
            risk_category="financial",
            summary_text="Financial risk indicated.",
            snippet="Debt levels increased year over year.",
            score=0.8,
            extracted_at=now,
        ),
    ]

    summary = _build_risk_summary("company-1", "Acme", evidence)

    assert summary.evidence_available is True
    assert summary.categories[0].category == "financial"
    assert summary.categories[0].count == 2
    assert summary.citations
    assert summary.citations[0].chunk_id == "chunk-1"


def test_build_risk_summary_handles_empty_evidence() -> None:
    summary = _build_risk_summary("company-1", "Acme", [])

    assert summary.evidence_available is False
    assert summary.categories == []
    assert summary.citations == []


def test_requires_human_review_when_confidence_is_low_or_citations_missing() -> None:
    assert _requires_human_review(confidence=0.5, citation_count=2, answer="Summary") is True
    assert _requires_human_review(confidence=0.9, citation_count=0, answer="Summary") is True
    assert (
        _requires_human_review(
            confidence=0.9,
            citation_count=2,
            answer="Not enough information in the retrieved context.",
        )
        is True
    )
    assert _requires_human_review(confidence=0.9, citation_count=2, answer="Grounded summary.") is False


def test_summarize_chunk_text_truncates_long_text() -> None:
    text = "word " * 100
    summary = summarize_chunk_text(text, max_length=40)

    assert len(summary) <= 40

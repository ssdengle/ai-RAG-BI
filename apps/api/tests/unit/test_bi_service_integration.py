from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from apps.api.app.core.errors import DomainError
from apps.api.app.domain.bi import (
    CompanyProfile,
    CompanyProfileDetail,
    CompetitorRelationship,
    ExecutiveBrief,
    RiskSummary,
    TrendSummary,
)
from apps.api.app.domain.retrieval import AssembledContext, Citation, QuestionAnswerResult, RetrievalResult, RetrievedChunk
from apps.api.app.services.company_profile_service import CompanyProfileService
from apps.api.app.services.competitor_service import CompetitorService
from apps.api.app.services.executive_brief_service import ExecutiveBriefService
from apps.api.app.services.market_trend_service import MarketTrendService
from apps.api.app.services.risk_tracking_service import RiskTrackingService


NOW = datetime.now(timezone.utc)


class _FakeSession:
    def __init__(self) -> None:
        self.committed = False

    async def commit(self) -> None:
        self.committed = True


class _FakeBiRepository:
    def __init__(self) -> None:
        self.profiles = {
            "company-1": CompanyProfile(
                company_id="company-1",
                name="Acme",
                display_name="Acme Corp",
                industry="Manufacturing",
                description=None,
                metadata={},
                created_at=NOW,
                updated_at=NOW,
            ),
            "company-2": CompanyProfile(
                company_id="company-2",
                name="Globex",
                display_name="Globex Inc",
                industry="Technology",
                description=None,
                metadata={},
                created_at=NOW,
                updated_at=NOW,
            ),
        }
        self.committed = False

    async def create_company_profile(self, session, *, name, display_name, industry=None, description=None, metadata=None):
        profile = CompanyProfile(
            company_id="company-new",
            name=name,
            display_name=display_name,
            industry=industry,
            description=description,
            metadata=metadata or {},
            created_at=NOW,
            updated_at=NOW,
        )
        self.profiles[profile.company_id] = profile
        return profile

    async def get_company_profile_by_name(self, session, name):
        for profile in self.profiles.values():
            if profile.name == name:
                return profile
        return None

    async def list_company_profiles(self, session):
        return list(self.profiles.values())

    async def get_company_profile(self, session, company_id):
        return self.profiles.get(company_id)

    async def get_company_profile_detail(self, session, company_id):
        profile = self.profiles.get(company_id)
        if profile is None:
            return None
        return CompanyProfileDetail(
            profile=profile,
            document_count=2,
            documents_by_type={"10-K": 1, "10-Q": 1},
            total_chunks=6,
            indexed_document_count=2,
            documents=[],
        )

    async def add_competitor_relationship(self, session, *, company_id, competitor_company_id, relationship_type=None, notes=None):
        return CompetitorRelationship(
            relationship_id="rel-1",
            company_id=company_id,
            competitor_company_id=competitor_company_id,
            competitor_name=self.profiles[competitor_company_id].display_name,
            relationship_type=relationship_type,
            notes=notes,
            created_at=NOW,
        )

    async def list_competitor_relationships(self, session, *, company_id):
        return [
            CompetitorRelationship(
                relationship_id="rel-1",
                company_id=company_id,
                competitor_company_id="company-2",
                competitor_name="Globex Inc",
                relationship_type="direct",
                notes=None,
                created_at=NOW,
            )
        ]

    async def replace_risk_evidence(self, session, *, company_id, evidence_items):
        return list(evidence_items)

    async def list_risk_evidence(self, session, *, company_id):
        return []

    async def replace_trend_evidence(self, session, *, company_id, evidence_items):
        return list(evidence_items)

    async def list_trend_evidence(self, session, **kwargs):
        return []

    async def get_company_metrics(self, session, *, company_id):
        profile = self.profiles.get(company_id)
        if profile is None:
            return None
        return profile, [], {"10-K": 1}


class _FakeRetrievalService:
    async def retrieve(self, session, *, query, mode, filters, top_k):
        chunk = RetrievedChunk(
            chunk_id="chunk-1",
            document_id="doc-1",
            document_title="Annual Report",
            text="Revenue increased while competition intensified and cyber security risks remain.",
            score=0.91,
            document_metadata={"company": filters.company or "Acme", "document_type": "10-K", "date": "2024-03-01"},
        )
        citation = Citation(
            document_id="doc-1",
            title="Annual Report",
            chunk_id="chunk-1",
            page_number=2,
            score=0.91,
            snippet="Revenue increased while competition intensified.",
        )
        return RetrievalResult(
            mode=mode,
            query=query,
            chunks=[chunk],
            citations=[citation],
            total_candidates=1,
        )


class _EmptyRetrievalService:
    async def retrieve(self, session, *, query, mode, filters, top_k):
        return RetrievalResult(
            mode=mode,
            query=query,
            chunks=[],
            citations=[],
            total_candidates=0,
        )


class _FakeQuestionAnsweringService:
    def __init__(self, *, empty: bool = False) -> None:
        self.empty = empty

    async def answer(self, session, *, question, mode, filters, top_k):
        if self.empty:
            return QuestionAnswerResult(
                answer="Not enough information in the retrieved context.",
                citations=[],
                confidence=0.0,
                retrieval=RetrievalResult(mode=mode, query=question, chunks=[], citations=[], total_candidates=0),
                context=AssembledContext(text="", citations=[], chunk_count=0, truncated=False),
                llm_provider=None,
                llm_model=None,
                finish_reason=None,
            )

        citation = Citation(
            document_id="doc-1",
            title="Annual Report",
            chunk_id="chunk-1",
            page_number=2,
            score=0.91,
            snippet="Revenue increased while competition intensified.",
        )
        return QuestionAnswerResult(
            answer="Acme revenue increased while competitive pressure remains elevated.",
            citations=[citation],
            confidence=0.91,
            retrieval=RetrievalResult(
                mode=mode,
                query=question,
                chunks=[],
                citations=[citation],
                total_candidates=1,
            ),
            context=AssembledContext(
                text="Revenue increased while competition intensified.",
                citations=[citation],
                chunk_count=1,
                truncated=False,
            ),
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            finish_reason="stop",
        )


def test_company_profile_service_creates_and_returns_profile_detail() -> None:
    repository = _FakeBiRepository()
    service = CompanyProfileService(bi_repository=repository)
    session = _FakeSession()

    created = asyncio.run(
        service.create_company_profile(
            session,
            name="NewCo",
            display_name="NewCo Ltd",
        )
    )
    detail = asyncio.run(service.get_company_profile(session, company_id="company-1"))

    assert created.company_id == "company-new"
    assert detail.document_count == 2


def test_company_profile_service_raises_when_profile_missing() -> None:
    service = CompanyProfileService(bi_repository=_FakeBiRepository())

    with pytest.raises(DomainError) as exc_info:
        asyncio.run(service.get_company_profile(None, company_id="missing"))

    assert exc_info.value.code == "company_profile_not_found"


def test_competitor_service_compare_companies_returns_metrics_and_citations() -> None:
    service = CompetitorService(
        bi_repository=_FakeBiRepository(),
        retrieval_service=_FakeRetrievalService(),
    )

    result = asyncio.run(
        service.compare_companies(
            None,
            company_ids=["company-1", "company-2"],
            query="competitive positioning",
        )
    )

    assert len(result.companies) == 2
    assert result.citations


def test_risk_tracking_service_summarize_handles_empty_evidence() -> None:
    service = RiskTrackingService(
        bi_repository=_FakeBiRepository(),
        retrieval_service=_EmptyRetrievalService(),
    )

    summary = asyncio.run(
        service.summarize_risks(_FakeSession(), company_id="company-1", refresh=True)
    )

    assert isinstance(summary, RiskSummary)
    assert summary.evidence_available is False


def test_market_trend_service_summarize_handles_empty_evidence() -> None:
    service = MarketTrendService(
        bi_repository=_FakeBiRepository(),
        retrieval_service=_EmptyRetrievalService(),
    )

    summary = asyncio.run(
        service.summarize_trends(
            _FakeSession(),
            company_id="company-1",
            refresh=True,
        )
    )

    assert isinstance(summary, TrendSummary)
    assert summary.evidence_available is False


def test_executive_brief_service_preserves_citations_and_flags_human_review_for_empty_evidence() -> None:
    service = ExecutiveBriefService(
        bi_repository=_FakeBiRepository(),
        question_answering_service=_FakeQuestionAnsweringService(empty=True),
    )

    brief = asyncio.run(
        service.generate_executive_brief(
            None,
            topic="Competitive outlook",
            company_id="company-1",
        )
    )

    assert isinstance(brief, ExecutiveBrief)
    assert brief.citations == []
    assert brief.human_review_recommended is True


def test_executive_brief_service_returns_grounded_brief_with_citations() -> None:
    service = ExecutiveBriefService(
        bi_repository=_FakeBiRepository(),
        question_answering_service=_FakeQuestionAnsweringService(),
    )

    brief = asyncio.run(
        service.generate_executive_brief(
            None,
            topic="Competitive outlook",
            company_id="company-1",
        )
    )

    assert brief.citations
    assert brief.confidence == 0.91
    assert brief.human_review_recommended is False

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from apps.api.app.agents.competitor_intelligence import CompetitorIntelligenceAgent
from apps.api.app.agents.critic import CriticAgent
from apps.api.app.agents.document_discovery import DocumentDiscoveryAgent
from apps.api.app.agents.executive_brief import ExecutiveBriefAgent
from apps.api.app.agents.market_intelligence import MarketIntelligenceAgent
from apps.api.app.agents.planner import PlannerAgent
from apps.api.app.agents.risk_analysis import RiskAnalysisAgent
from apps.api.app.agents.runtime import WorkflowRuntimeContext
from apps.api.app.domain.bi import (
    CompanyComparisonMetric,
    CompanyComparisonResult,
    CompanyProfile,
    CompanyProfileDetail,
    ExecutiveBrief,
    RiskCategorySummary,
    RiskSummary,
    TrendSummary,
    TrendTopicSummary,
)
from apps.api.app.domain.documents import DocumentBrowsePage
from apps.api.app.domain.retrieval import Citation, RetrievalResult, RetrievedChunk
from apps.api.tests.conftest import build_persisted_document


NOW = datetime.now(timezone.utc)


class _FakeSession:
    async def commit(self) -> None:
        return None


class _FakeKnowledgeBaseService:
    async def browse_documents(self, session, *, query):
        document = build_persisted_document(
            document_id="doc-1",
            attributes={"company": "Acme", "document_type": "10-K"},
        )
        return DocumentBrowsePage(items=[document], total=1, page=1, page_size=10)


class _FakeCompanyProfileService:
    async def list_company_profiles(self, session):
        return [
            CompanyProfile(
                company_id="company-1",
                name="Acme",
                display_name="Acme Corp",
                industry="Manufacturing",
                description=None,
                metadata={},
                created_at=NOW,
                updated_at=NOW,
            )
        ]

    async def get_company_profile(self, session, *, company_id):
        return CompanyProfileDetail(
            profile=CompanyProfile(
                company_id=company_id,
                name="Acme",
                display_name="Acme Corp",
                industry="Manufacturing",
                description=None,
                metadata={},
                created_at=NOW,
                updated_at=NOW,
            ),
            document_count=1,
            documents_by_type={"10-K": 1},
            total_chunks=2,
            indexed_document_count=1,
            documents=[],
        )


class _FakeRetrievalService:
    async def retrieve(self, session, *, query, mode, filters, top_k):
        chunk = RetrievedChunk(
            chunk_id="chunk-1",
            document_id="doc-1",
            document_title="Annual Report",
            text="Revenue increased while competition intensified.",
            score=0.91,
            document_metadata={"company": "Acme", "document_type": "10-K"},
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


class _FakeMarketTrendService:
    async def summarize_trends(self, session, **kwargs):
        citation = Citation(
            document_id="doc-1",
            title="Annual Report",
            chunk_id="chunk-1",
            page_number=2,
            score=0.87,
            snippet="Revenue increased steadily.",
        )
        return TrendSummary(
            company_id=kwargs.get("company_id"),
            company_name="Acme Corp",
            document_type=None,
            date_from=None,
            date_to=None,
            total_evidence_count=1,
            topics=[
                TrendTopicSummary(
                    topic="revenue_growth",
                    count=1,
                    document_types={"10-K": 1},
                    top_snippets=["Revenue increased steadily."],
                    average_score=0.87,
                )
            ],
            citations=[citation],
            evidence_available=True,
        )


class _FakeCompetitorService:
    async def compare_companies(self, session, *, company_ids, query, mode="hybrid", top_k=5):
        citation = Citation(
            document_id="doc-1",
            title="Annual Report",
            chunk_id="chunk-1",
            page_number=2,
            score=0.9,
            snippet="Competitive pressure remains elevated.",
        )
        return CompanyComparisonResult(
            companies=[
                CompanyComparisonMetric(
                    company_id=company_ids[0],
                    company_name="Acme Corp",
                    document_count=1,
                    total_chunks=2,
                    indexed_document_count=1,
                    top_document_types={"10-K": 1},
                    evidence_snippets=["Competitive pressure remains elevated."],
                ),
                CompanyComparisonMetric(
                    company_id=company_ids[1],
                    company_name="Globex Inc",
                    document_count=1,
                    total_chunks=2,
                    indexed_document_count=1,
                    top_document_types={"10-K": 1},
                    evidence_snippets=["Market share gains continued."],
                ),
            ],
            comparison_query=query,
            shared_topics=["competitive"],
            citations=[citation],
        )


class _FakeRiskTrackingService:
    async def summarize_risks(self, session, *, company_id, refresh=False, mode="hybrid", top_k=8):
        citation = Citation(
            document_id="doc-1",
            title="Annual Report",
            chunk_id="chunk-1",
            page_number=3,
            score=0.88,
            snippet="Liquidity pressure remains elevated.",
        )
        return RiskSummary(
            company_id=company_id,
            company_name="Acme Corp",
            total_evidence_count=1,
            categories=[
                RiskCategorySummary(
                    category="financial",
                    count=1,
                    top_snippets=["Liquidity pressure remains elevated."],
                    average_score=0.88,
                )
            ],
            citations=[citation],
            evidence_available=True,
        )


class _FakeExecutiveBriefService:
    async def generate_executive_brief(self, session, *, topic, company_id=None, mode="hybrid", top_k=6):
        citation = Citation(
            document_id="doc-1",
            title="Annual Report",
            chunk_id="chunk-1",
            page_number=2,
            score=0.91,
            snippet="Revenue increased while competition intensified.",
        )
        return ExecutiveBrief(
            title=f"Acme Corp: {topic}",
            summary="Acme revenue increased while competitive pressure remains elevated.",
            key_points=["Revenue increased", "Competitive pressure remains elevated"],
            citations=[citation],
            confidence=0.91,
            human_review_recommended=False,
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            company_id=company_id,
            company_name="Acme Corp",
            topic=topic,
        )


def build_fake_runtime(**overrides):
    session = _FakeSession()
    defaults = {
        "session": session,
        "retrieval_service": _FakeRetrievalService(),
        "question_answering_service": SimpleNamespace(),
        "knowledge_base_service": _FakeKnowledgeBaseService(),
        "company_profile_service": _FakeCompanyProfileService(),
        "competitor_service": _FakeCompetitorService(),
        "risk_tracking_service": _FakeRiskTrackingService(),
        "market_trend_service": _FakeMarketTrendService(),
        "executive_brief_service": _FakeExecutiveBriefService(),
    }
    defaults.update(overrides)
    return WorkflowRuntimeContext(**defaults)


def test_planner_agent_builds_branching_plan_for_risk_and_market_request() -> None:
    runtime = build_fake_runtime()
    result = asyncio.run(
        PlannerAgent(runtime).run(
            {"user_request": "Summarize market trends and key risks for Acme", "workflow_id": "wf-1"}
        )
    )

    assert result.success is True
    assert "document_discovery" in result.output["plan"]
    assert "market_intelligence" in result.output["plan"]
    assert "risk_analysis" in result.output["plan"]
    assert "executive_brief" in result.output["plan"]


def test_document_discovery_agent_returns_retrieval_citations() -> None:
    runtime = build_fake_runtime()
    result = asyncio.run(
        DocumentDiscoveryAgent(runtime).run(
            {
                "workflow_id": "wf-1",
                "user_request": "Find relevant filings",
                "topic": "filings",
                "company_id": "company-1",
            }
        )
    )

    assert result.citations
    assert "hybrid_retrieval" in result.metadata.tool_calls


def test_market_intelligence_agent_reuses_market_trend_service() -> None:
    runtime = build_fake_runtime()
    result = asyncio.run(
        MarketIntelligenceAgent(runtime).run(
            {"workflow_id": "wf-1", "user_request": "market trends", "company_id": "company-1"}
        )
    )

    assert result.output["evidence_available"] is True
    assert result.citations


def test_competitor_agent_skips_when_only_one_company_is_available() -> None:
    runtime = build_fake_runtime()
    result = asyncio.run(
        CompetitorIntelligenceAgent(runtime).run(
            {
                "workflow_id": "wf-1",
                "user_request": "compare competitors",
                "company_id": "company-1",
                "company_ids": ["company-1"],
            }
        )
    )

    assert result.output["skipped"] is True


def test_risk_analysis_agent_returns_empty_summary_without_company() -> None:
    runtime = build_fake_runtime()
    result = asyncio.run(
        RiskAnalysisAgent(runtime).run({"workflow_id": "wf-1", "user_request": "risks"})
    )

    assert result.output["evidence_available"] is False


def test_executive_brief_agent_returns_grounded_brief() -> None:
    runtime = build_fake_runtime()
    result = asyncio.run(
        ExecutiveBriefAgent(runtime).run(
            {
                "workflow_id": "wf-1",
                "user_request": "Prepare brief",
                "topic": "Competitive outlook",
                "company_id": "company-1",
            }
        )
    )

    assert result.output["summary"]
    assert result.citations
    assert result.confidence > 0


def test_critic_agent_flags_human_review_for_weak_evidence() -> None:
    runtime = build_fake_runtime()
    result = asyncio.run(
        CriticAgent(runtime).run(
            {
                "workflow_id": "wf-1",
                "confidence": 0.2,
                "citations": [],
                "retry_count": 0,
                "max_retries": 2,
                "agent_outputs": {
                    "executive_brief": {
                        "summary": "Not enough information in the retrieved context.",
                        "human_review_recommended": True,
                    }
                },
            }
        )
    )

    assert result.output["human_review_required"] is True
    assert result.output["needs_retry"] is True

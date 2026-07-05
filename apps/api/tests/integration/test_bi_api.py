from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from apps.api.app.api.bi import (
    get_company_profile_service,
    get_competitor_service,
    get_executive_brief_service,
    get_market_trend_service,
    get_risk_tracking_service,
)
from apps.api.app.core.database import get_db_session
from apps.api.app.domain.bi import (
    CompanyComparisonMetric,
    CompanyComparisonResult,
    CompanyProfile,
    CompanyProfileDetail,
    CompetitorRelationship,
    ExecutiveBrief,
    RiskCategorySummary,
    RiskComparisonResult,
    RiskSummary,
    TrendSummary,
    TrendTopicSummary,
)
from apps.api.app.domain.retrieval import Citation
from apps.api.app.main import create_app
from apps.api.tests.conftest import FakeDatabaseManager, FakeRedisManager, build_test_settings


NOW = datetime.now(timezone.utc)


class _FakeCompanyProfileService:
    async def create_company_profile(self, session, *, name, display_name, industry=None, description=None, metadata=None):
        return CompanyProfile(
            company_id="company-1",
            name=name,
            display_name=display_name,
            industry=industry,
            description=description,
            metadata=metadata or {},
            created_at=NOW,
            updated_at=NOW,
        )

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
            document_count=2,
            documents_by_type={"10-K": 1, "10-Q": 1},
            total_chunks=6,
            indexed_document_count=2,
            documents=[],
        )


class _FakeCompetitorService:
    async def add_competitor(self, session, *, company_id, competitor_company_id, relationship_type=None, notes=None):
        return CompetitorRelationship(
            relationship_id="rel-1",
            company_id=company_id,
            competitor_company_id=competitor_company_id,
            competitor_name="Globex Inc",
            relationship_type=relationship_type,
            notes=notes,
            created_at=NOW,
        )

    async def list_competitors(self, session, *, company_id):
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

    async def compare_companies(self, session, *, company_ids, query, mode="hybrid", top_k=5):
        citation = Citation(
            document_id="doc-1",
            title="Annual Report",
            chunk_id="chunk-1",
            page_number=2,
            score=0.9,
            snippet="Revenue increased while competition intensified.",
        )
        return CompanyComparisonResult(
            companies=[
                CompanyComparisonMetric(
                    company_id=company_ids[0],
                    company_name="Acme Corp",
                    document_count=2,
                    total_chunks=6,
                    indexed_document_count=2,
                    top_document_types={"10-K": 1},
                    evidence_snippets=["Revenue increased while competition intensified."],
                ),
                CompanyComparisonMetric(
                    company_id=company_ids[1],
                    company_name="Globex Inc",
                    document_count=1,
                    total_chunks=3,
                    indexed_document_count=1,
                    top_document_types={"10-K": 1},
                    evidence_snippets=["Market share gains continued."],
                ),
            ],
            comparison_query=query,
            shared_topics=["revenue"],
            citations=[citation],
        )


class _FakeRiskTrackingService:
    async def summarize_risks(self, session, *, company_id, refresh=False, mode="hybrid", top_k=8):
        if company_id == "empty-company":
            return RiskSummary(
                company_id=company_id,
                company_name="Empty Co",
                total_evidence_count=0,
                categories=[],
                citations=[],
                evidence_available=False,
            )
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
            total_evidence_count=2,
            categories=[
                RiskCategorySummary(
                    category="financial",
                    count=2,
                    top_snippets=["Liquidity pressure remains elevated."],
                    average_score=0.88,
                )
            ],
            citations=[citation],
            evidence_available=True,
        )

    async def compare_risks(self, session, *, company_ids, refresh=False, mode="hybrid", top_k=8):
        summaries = [
            await self.summarize_risks(session, company_id=company_id)
            for company_id in company_ids
        ]
        return RiskComparisonResult(
            companies=summaries,
            shared_categories=["financial"],
            unique_categories_by_company={company_ids[0]: [], company_ids[1]: []},
        )


class _FakeMarketTrendService:
    async def summarize_trends(self, session, **kwargs):
        if kwargs.get("company_id") == "empty-company":
            return TrendSummary(
                company_id="empty-company",
                company_name="Empty Co",
                document_type=kwargs.get("document_type"),
                date_from=kwargs.get("date_from"),
                date_to=kwargs.get("date_to"),
                total_evidence_count=0,
                topics=[],
                citations=[],
                evidence_available=False,
            )
        citation = Citation(
            document_id="doc-1",
            title="Annual Report",
            chunk_id="chunk-1",
            page_number=4,
            score=0.87,
            snippet="Revenue increased steadily across all regions.",
        )
        return TrendSummary(
            company_id=kwargs.get("company_id"),
            company_name="Acme Corp",
            document_type=kwargs.get("document_type"),
            date_from=kwargs.get("date_from"),
            date_to=kwargs.get("date_to"),
            total_evidence_count=1,
            topics=[
                TrendTopicSummary(
                    topic="revenue_growth",
                    count=1,
                    document_types={"10-K": 1},
                    top_snippets=["Revenue increased steadily across all regions."],
                    average_score=0.87,
                )
            ],
            citations=[citation],
            evidence_available=True,
        )


class _FakeExecutiveBriefService:
    async def generate_executive_brief(self, session, *, topic, company_id=None, mode="hybrid", top_k=6):
        if company_id == "empty-company":
            return ExecutiveBrief(
                title=f"Empty Co: {topic}",
                summary="Not enough information in the retrieved context.",
                key_points=["Not enough information in the retrieved context."],
                citations=[],
                confidence=0.0,
                human_review_recommended=True,
                llm_provider=None,
                llm_model=None,
                company_id=company_id,
                company_name="Empty Co",
                topic=topic,
            )
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
            key_points=["Acme revenue increased while competitive pressure remains elevated."],
            citations=[citation],
            confidence=0.91,
            human_review_recommended=False,
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            company_id=company_id,
            company_name="Acme Corp",
            topic=topic,
        )


async def _override_db_session():
    yield None


def _build_test_app():
    app = create_app(
        settings=build_test_settings(),
        database_manager=FakeDatabaseManager(),
        redis_manager=FakeRedisManager(),
        perform_startup_checks=False,
    )
    app.dependency_overrides[get_db_session] = _override_db_session
    app.dependency_overrides[get_company_profile_service] = lambda: _FakeCompanyProfileService()
    app.dependency_overrides[get_competitor_service] = lambda: _FakeCompetitorService()
    app.dependency_overrides[get_risk_tracking_service] = lambda: _FakeRiskTrackingService()
    app.dependency_overrides[get_market_trend_service] = lambda: _FakeMarketTrendService()
    app.dependency_overrides[get_executive_brief_service] = lambda: _FakeExecutiveBriefService()
    return app


def test_list_company_profiles_endpoint() -> None:
    with TestClient(_build_test_app()) as client:
        response = client.get("/v1/bi/companies")

    assert response.status_code == 200
    assert response.json()[0]["name"] == "Acme"


def test_get_company_profile_endpoint() -> None:
    with TestClient(_build_test_app()) as client:
        response = client.get("/v1/bi/companies/company-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_count"] == 2
    assert payload["documents_by_type"]["10-K"] == 1


def test_compare_companies_endpoint_preserves_citations() -> None:
    with TestClient(_build_test_app()) as client:
        response = client.post(
            "/v1/bi/companies/compare",
            json={
                "company_ids": ["company-1", "company-2"],
                "query": "competitive positioning",
                "mode": "hybrid",
                "top_k": 5,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["companies"]) == 2
    assert payload["citations"][0]["chunk_id"] == "chunk-1"


def test_summarize_risks_endpoint() -> None:
    with TestClient(_build_test_app()) as client:
        response = client.post(
            "/v1/bi/companies/company-1/risks/summarize",
            json={"refresh": False, "mode": "hybrid", "top_k": 8},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["evidence_available"] is True
    assert payload["categories"][0]["category"] == "financial"


def test_compare_risks_endpoint() -> None:
    with TestClient(_build_test_app()) as client:
        response = client.post(
            "/v1/bi/risks/compare",
            json={"company_ids": ["company-1", "company-2"], "refresh": False},
        )

    assert response.status_code == 200
    assert response.json()["shared_categories"] == ["financial"]


def test_summarize_market_trends_endpoint() -> None:
    with TestClient(_build_test_app()) as client:
        response = client.post(
            "/v1/bi/trends/summarize",
            json={
                "company_id": "company-1",
                "document_type": "10-K",
                "date_from": "2024-01-01",
                "date_to": "2024-12-31",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["topics"][0]["topic"] == "revenue_growth"
    assert payload["citations"][0]["chunk_id"] == "chunk-1"


def test_generate_executive_brief_endpoint() -> None:
    with TestClient(_build_test_app()) as client:
        response = client.post(
            "/v1/bi/briefs/executive",
            json={"topic": "Competitive outlook", "company_id": "company-1"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["citations"][0]["chunk_id"] == "chunk-1"
    assert payload["human_review_recommended"] is False


def test_empty_evidence_endpoints_flag_review_or_empty_summaries() -> None:
    with TestClient(_build_test_app()) as client:
        risk_response = client.post(
            "/v1/bi/companies/empty-company/risks/summarize",
            json={"refresh": True},
        )
        trend_response = client.post(
            "/v1/bi/trends/summarize",
            json={"company_id": "empty-company"},
        )
        brief_response = client.post(
            "/v1/bi/briefs/executive",
            json={"topic": "Outlook", "company_id": "empty-company"},
        )

    assert risk_response.json()["evidence_available"] is False
    assert trend_response.json()["evidence_available"] is False
    assert brief_response.json()["human_review_recommended"] is True
    assert brief_response.json()["citations"] == []

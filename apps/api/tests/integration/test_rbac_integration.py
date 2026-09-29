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
from apps.api.app.api.documents import get_knowledge_base_service
from apps.api.app.core.config import AuthSettings, SecuritySettings
from apps.api.app.core.database import get_db_session
from apps.api.app.domain.bi import (
    CompanyProfile,
    CompanyProfileDetail,
    CompetitorRelationship,
    ExecutiveBrief,
    RiskCategorySummary,
    RiskSummary,
    TrendSummary,
    TrendTopicSummary,
)
from apps.api.app.domain.documents import DocumentBrowsePage, IndexingStatus, IndexingVisibilityView
from apps.api.app.domain.retrieval import Citation
from apps.api.app.main import create_app
from apps.api.tests.conftest import (
    FakeDatabaseManager,
    FakeRedisManager,
    build_persisted_chunk,
    build_persisted_document,
    build_test_settings,
)


NOW = datetime.now(timezone.utc)
VIEWER_HEADERS = {"X-API-Key": "viewer-key"}
ANALYST_HEADERS = {"X-API-Key": "analyst-key"}
ADMIN_HEADERS = {"X-API-Key": "admin-key"}


class _FakeKnowledgeBaseService:
    async def browse_documents(self, session, *, query):
        return DocumentBrowsePage(items=[], total=0, page=query.page, page_size=query.page_size)

    async def get_document_chunk(self, session, *, document_id, chunk_id):
        return build_persisted_chunk(chunk_id=chunk_id, document_id=document_id)

    async def get_indexing_visibility(self, session, *, document_id):
        document = build_persisted_document(document_id=document_id, indexing_status=IndexingStatus.INDEXED)
        return IndexingVisibilityView(
            document=document,
            embedding_count=1,
            failed_chunks=[],
            retry_eligible=False,
        )


class _FakeCompanyProfileService:
    async def create_company_profile(self, session, *, name, display_name, industry=None, description=None, metadata=None):
        return CompanyProfile(
            company_id="company-new",
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
            document_count=1,
            documents_by_type={"10-K": 1},
            total_chunks=3,
            indexed_document_count=1,
            documents=[],
        )


class _FakeCompetitorService:
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


class _FakeRiskTrackingService:
    async def summarize_risks(self, session, *, company_id, refresh=False, mode="hybrid", top_k=8):
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
            citations=[],
            evidence_available=True,
        )


class _FakeMarketTrendService:
    async def summarize_trends(self, session, **kwargs):
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
                    top_snippets=["Revenue increased steadily."],
                    average_score=0.87,
                )
            ],
            citations=[],
            evidence_available=True,
        )


class _FakeExecutiveBriefService:
    async def generate_executive_brief(self, session, *, topic, company_id=None, mode="hybrid", top_k=6):
        return ExecutiveBrief(
            title=f"Acme Corp: {topic}",
            summary="Acme revenue increased while competitive pressure remains elevated.",
            key_points=["Acme revenue increased while competitive pressure remains elevated."],
            citations=[
                Citation(
                    document_id="doc-1",
                    title="Annual Report",
                    chunk_id="chunk-1",
                    page_number=2,
                    score=0.91,
                    snippet="Revenue increased while competition intensified.",
                )
            ],
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


def _build_auth_app():
    settings = build_test_settings()
    settings = settings.model_copy(
        update={
            "auth": AuthSettings(enabled=True),
            "security": SecuritySettings(rate_limit_enabled=False, block_prompt_injection=False),
        }
    )
    app = create_app(
        settings=settings,
        database_manager=FakeDatabaseManager(),
        redis_manager=FakeRedisManager(),
        perform_startup_checks=False,
    )
    app.dependency_overrides[get_db_session] = _override_db_session
    app.dependency_overrides[get_knowledge_base_service] = lambda: _FakeKnowledgeBaseService()
    app.dependency_overrides[get_company_profile_service] = lambda: _FakeCompanyProfileService()
    app.dependency_overrides[get_competitor_service] = lambda: _FakeCompetitorService()
    app.dependency_overrides[get_risk_tracking_service] = lambda: _FakeRiskTrackingService()
    app.dependency_overrides[get_market_trend_service] = lambda: _FakeMarketTrendService()
    app.dependency_overrides[get_executive_brief_service] = lambda: _FakeExecutiveBriefService()
    return app


def test_viewer_can_access_bi_read_endpoints() -> None:
    with TestClient(_build_auth_app()) as client:
        list_companies = client.get("/v1/bi/companies", headers=VIEWER_HEADERS)
        list_competitors = client.get("/v1/bi/companies/company-1/competitors", headers=VIEWER_HEADERS)
        summarize_risks = client.post(
            "/v1/bi/companies/company-1/risks/summarize",
            headers=VIEWER_HEADERS,
            json={"refresh": False},
        )
        summarize_trends = client.post(
            "/v1/bi/trends/summarize",
            headers=VIEWER_HEADERS,
            json={"company_id": "company-1"},
        )
        executive_brief = client.post(
            "/v1/bi/briefs/executive",
            headers=VIEWER_HEADERS,
            json={"topic": "Competitive outlook", "company_id": "company-1"},
        )

    assert list_companies.status_code == 200
    assert list_competitors.status_code == 200
    assert summarize_risks.status_code == 200
    assert summarize_trends.status_code == 200
    assert executive_brief.status_code == 200


def test_viewer_can_access_document_read_endpoints() -> None:
    with TestClient(_build_auth_app()) as client:
        chunk_detail = client.get("/v1/documents/doc-1/chunks/chunk-1", headers=VIEWER_HEADERS)
        indexing_visibility = client.get(
            "/v1/documents/doc-1/indexing-visibility",
            headers=VIEWER_HEADERS,
        )

    assert chunk_detail.status_code == 200
    assert indexing_visibility.status_code == 200


def test_viewer_is_blocked_from_bi_write_and_admin_only_endpoints() -> None:
    with TestClient(_build_auth_app()) as client:
        create_company = client.post(
            "/v1/bi/companies",
            headers=VIEWER_HEADERS,
            json={"name": "NewCo", "display_name": "NewCo Ltd"},
        )
        create_dataset = client.post(
            "/v1/evaluation/datasets",
            headers=VIEWER_HEADERS,
            json={"name": "Benchmark", "description": "", "target_type": "grounded_qa"},
        )
        admin_only = client.get("/v1/internal/admin-only", headers=VIEWER_HEADERS)

    assert create_company.status_code == 403
    assert create_company.json()["code"] == "forbidden"
    assert create_dataset.status_code == 403
    assert create_dataset.json()["code"] == "forbidden"
    assert admin_only.status_code == 403
    assert admin_only.json()["code"] == "forbidden"


def test_analyst_can_access_bi_write_endpoints() -> None:
    with TestClient(_build_auth_app()) as client:
        response = client.post(
            "/v1/bi/companies",
            headers=ANALYST_HEADERS,
            json={"name": "NewCo", "display_name": "NewCo Ltd"},
        )

    assert response.status_code == 201


def test_reviewer_can_manage_workflows_but_not_run_evaluations() -> None:
    with TestClient(_build_auth_app()) as client:
        evaluation_response = client.post(
            "/v1/evaluation/datasets/dataset-1/runs",
            headers={"X-API-Key": "reviewer-key"},
            json={},
        )

    assert evaluation_response.status_code == 403
    assert evaluation_response.json()["code"] == "forbidden"

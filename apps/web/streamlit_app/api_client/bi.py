from __future__ import annotations

from typing import Any, Optional

from apps.web.streamlit_app.api_client.base import BaseApiClient
from apps.web.streamlit_app.api_client.models import (
    CompanyComparison,
    CompanyProfile,
    CompanyProfileDetail,
    CompetitorRelationship,
    ExecutiveBrief,
    RiskComparison,
    RiskSummary,
    TrendSummary,
)


class BusinessIntelligenceApiClient:
    def __init__(self, client: BaseApiClient) -> None:
        self._client = client

    def list_companies(self) -> list[CompanyProfile]:
        data = self._client.get_json("/v1/bi/companies")
        return [CompanyProfile.model_validate(item) for item in data]

    def create_company(
        self,
        *,
        name: str,
        display_name: str,
        industry: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> CompanyProfile:
        payload = {
            "name": name,
            "display_name": display_name,
            "industry": industry,
            "description": description,
            "metadata": metadata or {},
        }
        data = self._client.post_json("/v1/bi/companies", json=payload)
        return CompanyProfile.model_validate(data)

    def get_company(self, company_id: str) -> CompanyProfileDetail:
        data = self._client.get_json(f"/v1/bi/companies/{company_id}")
        return CompanyProfileDetail.model_validate(data)

    def add_competitor(
        self,
        company_id: str,
        *,
        competitor_company_id: str,
        relationship_type: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> CompetitorRelationship:
        payload = {
            "competitor_company_id": competitor_company_id,
            "relationship_type": relationship_type,
            "notes": notes,
        }
        data = self._client.post_json(f"/v1/bi/companies/{company_id}/competitors", json=payload)
        return CompetitorRelationship.model_validate(data)

    def list_competitors(self, company_id: str) -> list[CompetitorRelationship]:
        data = self._client.get_json(f"/v1/bi/companies/{company_id}/competitors")
        return [CompetitorRelationship.model_validate(item) for item in data]

    def compare_companies(
        self,
        *,
        company_ids: list[str],
        query: str,
        mode: str = "hybrid",
        top_k: int = 5,
    ) -> CompanyComparison:
        payload = {"company_ids": company_ids, "query": query, "mode": mode, "top_k": top_k}
        data = self._client.post_json("/v1/bi/companies/compare", json=payload)
        return CompanyComparison.model_validate(data)

    def summarize_risks(
        self,
        company_id: str,
        *,
        refresh: bool = False,
        mode: str = "hybrid",
        top_k: int = 8,
    ) -> RiskSummary:
        payload = {"refresh": refresh, "mode": mode, "top_k": top_k}
        data = self._client.post_json(f"/v1/bi/companies/{company_id}/risks/summarize", json=payload)
        return RiskSummary.model_validate(data)

    def compare_risks(
        self,
        *,
        company_ids: list[str],
        refresh: bool = False,
        mode: str = "hybrid",
        top_k: int = 8,
    ) -> RiskComparison:
        payload = {"company_ids": company_ids, "refresh": refresh, "mode": mode, "top_k": top_k}
        data = self._client.post_json("/v1/bi/risks/compare", json=payload)
        return RiskComparison.model_validate(data)

    def summarize_trends(
        self,
        *,
        company_id: Optional[str] = None,
        document_type: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        refresh: bool = False,
        mode: str = "hybrid",
        top_k: int = 8,
    ) -> TrendSummary:
        payload = {
            "company_id": company_id,
            "document_type": document_type,
            "date_from": date_from,
            "date_to": date_to,
            "refresh": refresh,
            "mode": mode,
            "top_k": top_k,
        }
        data = self._client.post_json("/v1/bi/trends/summarize", json=payload)
        return TrendSummary.model_validate(data)

    def generate_executive_brief(
        self,
        *,
        topic: str,
        company_id: Optional[str] = None,
        mode: str = "hybrid",
        top_k: int = 6,
    ) -> ExecutiveBrief:
        payload = {"topic": topic, "company_id": company_id, "mode": mode, "top_k": top_k}
        data = self._client.post_json("/v1/bi/briefs/executive", json=payload)
        return ExecutiveBrief.model_validate(data)

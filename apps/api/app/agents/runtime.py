from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.services.company_profile_service import CompanyProfileService
from apps.api.app.services.competitor_service import CompetitorService
from apps.api.app.services.executive_brief_service import ExecutiveBriefService
from apps.api.app.services.knowledge_base_service import KnowledgeBaseService
from apps.api.app.services.market_trend_service import MarketTrendService
from apps.api.app.services.question_answering_service import QuestionAnsweringService
from apps.api.app.services.retrieval_service import RetrievalService
from apps.api.app.services.risk_tracking_service import RiskTrackingService


@dataclass
class WorkflowRuntimeContext:
    session: AsyncSession
    retrieval_service: RetrievalService
    question_answering_service: QuestionAnsweringService
    knowledge_base_service: KnowledgeBaseService
    company_profile_service: CompanyProfileService
    competitor_service: CompetitorService
    risk_tracking_service: RiskTrackingService
    market_trend_service: MarketTrendService
    executive_brief_service: ExecutiveBriefService
    cancelled_workflow_ids: set[str] = field(default_factory=set)

    def is_cancelled(self, workflow_id: str) -> bool:
        return workflow_id in self.cancelled_workflow_ids

    def mark_cancelled(self, workflow_id: str) -> None:
        self.cancelled_workflow_ids.add(workflow_id)

    def clear_cancelled(self, workflow_id: str) -> None:
        self.cancelled_workflow_ids.discard(workflow_id)

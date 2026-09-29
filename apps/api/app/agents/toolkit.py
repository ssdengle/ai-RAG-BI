from __future__ import annotations

from apps.api.app.domain.documents import DocumentBrowseFilters, DocumentBrowseQuery
from apps.api.app.domain.retrieval import RetrievalFilters, RetrievalMode
from apps.api.app.agents.runtime import WorkflowRuntimeContext


class AgentToolkit:
    """Thin wrappers around existing platform services used as agent tools."""

    def __init__(self, runtime: WorkflowRuntimeContext) -> None:
        self._runtime = runtime

    async def document_search(
        self,
        *,
        search: str | None = None,
        company: str | None = None,
        document_type: str | None = None,
        page: int = 1,
        page_size: int = 10,
    ):
        return await self._runtime.knowledge_base_service.browse_documents(
            self._runtime.session,
            query=DocumentBrowseQuery(
                filters=DocumentBrowseFilters(
                    search=search,
                    company=company,
                    document_type=document_type,
                ),
                page=page,
                page_size=page_size,
            ),
        )

    async def hybrid_retrieval(
        self,
        *,
        query: str,
        company: str | None = None,
        document_type: str | None = None,
        top_k: int = 5,
        mode: RetrievalMode = "hybrid",
    ):
        return await self._runtime.retrieval_service.retrieve(
            self._runtime.session,
            query=query,
            mode=mode,
            filters=RetrievalFilters(company=company, document_type=document_type),
            top_k=top_k,
        )

    async def question_answering(
        self,
        *,
        question: str,
        company: str | None = None,
        top_k: int = 5,
        mode: RetrievalMode = "hybrid",
    ):
        return await self._runtime.question_answering_service.answer(
            self._runtime.session,
            question=question,
            mode=mode,
            filters=RetrievalFilters(company=company),
            top_k=top_k,
        )

    async def list_company_profiles(self):
        return await self._runtime.company_profile_service.list_company_profiles(
            self._runtime.session
        )

    async def get_company_profile(self, *, company_id: str):
        return await self._runtime.company_profile_service.get_company_profile(
            self._runtime.session,
            company_id=company_id,
        )

    async def compare_companies(
        self,
        *,
        company_ids: list[str],
        query: str,
        top_k: int = 5,
    ):
        return await self._runtime.competitor_service.compare_companies(
            self._runtime.session,
            company_ids=company_ids,
            query=query,
            top_k=top_k,
        )

    async def summarize_risks(self, *, company_id: str, refresh: bool = True, top_k: int = 8):
        return await self._runtime.risk_tracking_service.summarize_risks(
            self._runtime.session,
            company_id=company_id,
            refresh=refresh,
            top_k=top_k,
        )

    async def summarize_market_trends(
        self,
        *,
        company_id: str | None = None,
        document_type: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        refresh: bool = True,
        top_k: int = 8,
    ):
        return await self._runtime.market_trend_service.summarize_trends(
            self._runtime.session,
            company_id=company_id,
            document_type=document_type,
            date_from=date_from,
            date_to=date_to,
            refresh=refresh,
            top_k=top_k,
        )

    async def generate_executive_brief(
        self,
        *,
        topic: str,
        company_id: str | None = None,
        top_k: int = 6,
    ):
        return await self._runtime.executive_brief_service.generate_executive_brief(
            self._runtime.session,
            topic=topic,
            company_id=company_id,
            top_k=top_k,
        )

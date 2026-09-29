from __future__ import annotations

from apps.api.app.agents.base import AgentTimer, build_metadata
from apps.api.app.agents.runtime import WorkflowRuntimeContext
from apps.api.app.agents.toolkit import AgentToolkit
from apps.api.app.domain.workflows import AgentResult


class DocumentDiscoveryAgent:
    """Discovers relevant companies, selects documents, and requests retrieval."""

    def __init__(self, runtime: WorkflowRuntimeContext) -> None:
        self._runtime = runtime
        self._toolkit = AgentToolkit(runtime)

    async def run(self, state: dict) -> AgentResult:
        timer = AgentTimer()
        tool_calls = ["list_company_profiles", "document_search", "hybrid_retrieval"]

        profiles = await self._toolkit.list_company_profiles()
        company_name = None
        if state.get("company_id"):
            detail = await self._toolkit.get_company_profile(company_id=state["company_id"])
            company_name = detail.profile.name

        browse = await self._toolkit.document_search(
            search=state.get("topic"),
            company=company_name,
            page_size=10,
        )
        retrieval = await self._toolkit.hybrid_retrieval(
            query=state["user_request"],
            company=company_name,
            top_k=5,
        )

        return AgentResult(
            agent="document_discovery",
            success=True,
            output={
                "company_count": len(profiles),
                "document_count": browse.total,
                "selected_documents": [
                    {
                        "document_id": document.document_id,
                        "title": document.title,
                        "company": (document.attributes or {}).get("company"),
                    }
                    for document in browse.items
                ],
                "retrieval_candidates": retrieval.total_candidates,
            },
            confidence=min(max(retrieval.chunks[0].score, 0.0), 1.0) if retrieval.chunks else 0.0,
            citations=retrieval.citations,
            metadata=build_metadata(
                timer,
                tool_calls=tool_calls,
                retrieval_statistics={
                    "total_candidates": retrieval.total_candidates,
                    "returned_chunks": len(retrieval.chunks),
                },
            ),
        )

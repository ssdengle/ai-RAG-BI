from __future__ import annotations

from apps.api.app.agents.base import AgentTimer, build_metadata
from apps.api.app.agents.runtime import WorkflowRuntimeContext
from apps.api.app.agents.toolkit import AgentToolkit
from apps.api.app.domain.workflows import AgentResult


class CompetitorIntelligenceAgent:
    """Compares companies by reusing CompetitorService."""

    def __init__(self, runtime: WorkflowRuntimeContext) -> None:
        self._runtime = runtime
        self._toolkit = AgentToolkit(runtime)

    async def run(self, state: dict) -> AgentResult:
        timer = AgentTimer()
        tool_calls = ["compare_companies"]
        company_ids = list(state.get("company_ids") or [])
        if state.get("company_id") and state["company_id"] not in company_ids:
            company_ids.insert(0, state["company_id"])
        if len(company_ids) < 2:
            return AgentResult(
                agent="competitor_intelligence",
                success=True,
                output={"skipped": True, "reason": "At least two company IDs are required."},
                confidence=0.0,
                citations=[],
                metadata=build_metadata(timer, tool_calls=[]),
            )

        comparison = await self._toolkit.compare_companies(
            company_ids=company_ids[:2],
            query=state["user_request"],
        )

        confidence = 0.0
        if comparison.citations:
            confidence = round(
                sum(citation.score for citation in comparison.citations) / len(comparison.citations),
                4,
            )

        return AgentResult(
            agent="competitor_intelligence",
            success=True,
            output={
                "comparison_query": comparison.comparison_query,
                "shared_topics": comparison.shared_topics,
                "companies": [
                    {
                        "company_id": metric.company_id,
                        "company_name": metric.company_name,
                        "document_count": metric.document_count,
                    }
                    for metric in comparison.companies
                ],
            },
            confidence=confidence,
            citations=comparison.citations,
            metadata=build_metadata(
                timer,
                tool_calls=tool_calls,
                retrieval_statistics={"company_count": len(comparison.companies)},
            ),
        )

from __future__ import annotations

from apps.api.app.agents.base import AgentTimer, build_metadata
from apps.api.app.agents.runtime import WorkflowRuntimeContext
from apps.api.app.agents.toolkit import AgentToolkit
from apps.api.app.domain.workflows import AgentResult


class RiskAnalysisAgent:
    """Summarizes risks by reusing RiskTrackingService."""

    def __init__(self, runtime: WorkflowRuntimeContext) -> None:
        self._runtime = runtime
        self._toolkit = AgentToolkit(runtime)

    async def run(self, state: dict) -> AgentResult:
        timer = AgentTimer()
        tool_calls = ["summarize_risks"]
        company_id = state.get("company_id")
        if not company_id:
            return AgentResult(
                agent="risk_analysis",
                success=True,
                output={"evidence_available": False, "categories": []},
                confidence=0.0,
                citations=[],
                metadata=build_metadata(timer, tool_calls=tool_calls),
            )

        summary = await self._toolkit.summarize_risks(company_id=company_id, refresh=True)
        confidence = 0.0
        if summary.evidence_available and summary.categories:
            confidence = round(
                sum(category.average_score for category in summary.categories) / len(summary.categories),
                4,
            )

        return AgentResult(
            agent="risk_analysis",
            success=True,
            output={
                "evidence_available": summary.evidence_available,
                "categories": [
                    {
                        "category": category.category,
                        "count": category.count,
                    }
                    for category in summary.categories
                ],
            },
            confidence=confidence,
            citations=summary.citations,
            metadata=build_metadata(
                timer,
                tool_calls=tool_calls,
                retrieval_statistics={"total_evidence_count": summary.total_evidence_count},
            ),
        )

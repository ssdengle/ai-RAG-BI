from __future__ import annotations

from apps.api.app.agents.base import AgentTimer, build_metadata
from apps.api.app.agents.runtime import WorkflowRuntimeContext
from apps.api.app.agents.toolkit import AgentToolkit
from apps.api.app.domain.workflows import AgentResult


class MarketIntelligenceAgent:
    """Summarizes market trends by reusing MarketTrendService."""

    def __init__(self, runtime: WorkflowRuntimeContext) -> None:
        self._runtime = runtime
        self._toolkit = AgentToolkit(runtime)

    async def run(self, state: dict) -> AgentResult:
        timer = AgentTimer()
        tool_calls = ["summarize_market_trends"]
        company_id = state.get("company_id")

        summary = await self._toolkit.summarize_market_trends(
            company_id=company_id,
            refresh=True,
        )

        confidence = 0.0
        if summary.evidence_available and summary.topics:
            confidence = round(
                sum(topic.average_score for topic in summary.topics) / len(summary.topics),
                4,
            )

        return AgentResult(
            agent="market_intelligence",
            success=True,
            output={
                "evidence_available": summary.evidence_available,
                "topics": [
                    {
                        "topic": topic.topic,
                        "count": topic.count,
                        "document_types": topic.document_types,
                    }
                    for topic in summary.topics
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

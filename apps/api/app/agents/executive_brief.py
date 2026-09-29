from __future__ import annotations

from apps.api.app.agents.base import AgentTimer, build_metadata
from apps.api.app.agents.runtime import WorkflowRuntimeContext
from apps.api.app.agents.toolkit import AgentToolkit
from apps.api.app.domain.workflows import AgentResult


class ExecutiveBriefAgent:
    """Generates the final executive report by reusing ExecutiveBriefService."""

    def __init__(self, runtime: WorkflowRuntimeContext) -> None:
        self._runtime = runtime
        self._toolkit = AgentToolkit(runtime)

    async def run(self, state: dict) -> AgentResult:
        timer = AgentTimer()
        tool_calls = ["generate_executive_brief"]

        brief = await self._toolkit.generate_executive_brief(
            topic=state.get("topic") or state["user_request"],
            company_id=state.get("company_id"),
        )

        return AgentResult(
            agent="executive_brief",
            success=True,
            output={
                "title": brief.title,
                "summary": brief.summary,
                "key_points": brief.key_points,
                "human_review_recommended": brief.human_review_recommended,
            },
            confidence=brief.confidence,
            citations=brief.citations,
            metadata=build_metadata(
                timer,
                tool_calls=tool_calls,
                token_usage={
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                },
            ),
        )

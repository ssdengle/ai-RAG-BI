from __future__ import annotations

from apps.api.app.agents.base import AgentTimer, build_metadata
from apps.api.app.agents.runtime import WorkflowRuntimeContext
from apps.api.app.domain.workflows import EXECUTABLE_AGENTS, AgentResult


class PlannerAgent:
    """Analyzes the user request and builds a branching execution plan."""

    def __init__(self, runtime: WorkflowRuntimeContext) -> None:
        self._runtime = runtime

    async def run(self, state: dict) -> AgentResult:
        timer = AgentTimer()
        request = state["user_request"].lower()
        plan: list[str] = ["document_discovery"]

        if any(keyword in request for keyword in ("trend", "market", "growth")):
            plan.append("market_intelligence")
        if any(keyword in request for keyword in ("compare", "competitor", "versus", " vs ")):
            plan.append("competitor_intelligence")
        if "risk" in request:
            plan.append("risk_analysis")

        plan.append("executive_brief")
        plan = [step for step in plan if step in EXECUTABLE_AGENTS]

        return AgentResult(
            agent="planner",
            success=True,
            output={"plan": plan, "branching_enabled": len(plan) > 2},
            confidence=0.95,
            citations=[],
            metadata=build_metadata(timer, tool_calls=[]),
        )

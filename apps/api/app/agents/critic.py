from __future__ import annotations

from apps.api.app.agents.base import AgentTimer, build_metadata
from apps.api.app.agents.runtime import WorkflowRuntimeContext
from apps.api.app.domain.workflows import AgentResult


class CriticAgent:
    """Reviews final output, detects weak evidence, and recommends follow-up actions."""

    def __init__(self, runtime: WorkflowRuntimeContext) -> None:
        self._runtime = runtime

    async def run(self, state: dict) -> AgentResult:
        timer = AgentTimer()
        brief_output = (state.get("agent_outputs") or {}).get("executive_brief", {})
        citations = state.get("citations") or []
        confidence = float(state.get("confidence") or 0.0)
        summary = str(brief_output.get("summary") or "")

        unsupported_claims = []
        if summary and not citations:
            unsupported_claims.append("Final summary lacks supporting citations.")
        if summary.startswith("Not enough information"):
            unsupported_claims.append("Executive brief indicates insufficient retrieved evidence.")
        if confidence < 0.75:
            unsupported_claims.append("Overall confidence is below the human review threshold.")

        weak_evidence = confidence < 0.75 or len(citations) < 1
        needs_retry = weak_evidence and int(state.get("retry_count") or 0) < int(state.get("max_retries") or 2)
        human_review_required = weak_evidence or bool(brief_output.get("human_review_recommended"))

        return AgentResult(
            agent="critic",
            success=True,
            output={
                "weak_evidence": weak_evidence,
                "unsupported_claims": unsupported_claims,
                "needs_retry": needs_retry,
                "human_review_required": human_review_required,
                "recommended_actions": (
                    ["Run additional document discovery and retrieval."]
                    if needs_retry
                    else (["Route output to human review."] if human_review_required else [])
                ),
            },
            confidence=confidence,
            citations=[],
            metadata=build_metadata(timer, tool_calls=[]),
        )

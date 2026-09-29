from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from langgraph.graph import END, StateGraph

from apps.api.app.agents.base import merge_citations
from apps.api.app.agents.competitor_intelligence import CompetitorIntelligenceAgent
from apps.api.app.agents.critic import CriticAgent
from apps.api.app.agents.document_discovery import DocumentDiscoveryAgent
from apps.api.app.agents.executive_brief import ExecutiveBriefAgent
from apps.api.app.agents.market_intelligence import MarketIntelligenceAgent
from apps.api.app.agents.planner import PlannerAgent
from apps.api.app.agents.risk_analysis import RiskAnalysisAgent
from apps.api.app.agents.runtime import WorkflowRuntimeContext
from apps.api.app.core.logging import bind_context, get_logger
from apps.api.app.domain.workflows import EXECUTABLE_AGENTS, AgentResult
from apps.api.app.workflows.state import WorkflowGraphState

logger = get_logger("api.workflow.graph")

AGENT_RUNNERS = {
    "document_discovery": DocumentDiscoveryAgent,
    "market_intelligence": MarketIntelligenceAgent,
    "competitor_intelligence": CompetitorIntelligenceAgent,
    "risk_analysis": RiskAnalysisAgent,
    "executive_brief": ExecutiveBriefAgent,
}


def build_workflow_graph():
    graph = StateGraph(WorkflowGraphState)

    graph.add_node("planner", _planner_node)
    for agent_name in AGENT_RUNNERS:
        graph.add_node(agent_name, _make_agent_node(agent_name))
    graph.add_node("critic", _critic_node)
    graph.add_node("finalize", _finalize_node)

    graph.set_entry_point("planner")
    graph.add_conditional_edges("planner", _route_after_planner)
    for agent_name in AGENT_RUNNERS:
        graph.add_conditional_edges(agent_name, _route_after_agent)
    graph.add_conditional_edges("critic", _route_after_critic)
    graph.add_edge("finalize", END)

    return graph.compile()


async def _planner_node(state: WorkflowGraphState, config) -> dict[str, Any]:
    runtime: WorkflowRuntimeContext = config["configurable"]["runtime"]
    if runtime.is_cancelled(state["workflow_id"]):
        return {"cancelled": True, "status": "cancelled"}

    result = await PlannerAgent(runtime).run(dict(state))
    return _apply_agent_result(state, result, plan=result.output.get("plan", []))


def _make_agent_node(agent_name: str):
    async def _node(state: WorkflowGraphState, config) -> dict[str, Any]:
        runtime: WorkflowRuntimeContext = config["configurable"]["runtime"]
        if runtime.is_cancelled(state["workflow_id"]):
            return {"cancelled": True, "status": "cancelled"}

        agent_cls = AGENT_RUNNERS[agent_name]
        try:
            result = await agent_cls(runtime).run(dict(state))
            return _apply_agent_result(state, result)
        except Exception as exc:
            failed_steps = list(state.get("failed_steps") or [])
            if agent_name not in failed_steps:
                failed_steps.append(agent_name)
            errors = list(state.get("errors") or [])
            errors.append(str(exc))
            _log_agent_failure(state, agent_name, exc)
            return {
                "failed_steps": failed_steps,
                "errors": errors,
                "status": "failed",
            }

    return _node


async def _critic_node(state: WorkflowGraphState, config) -> dict[str, Any]:
    runtime: WorkflowRuntimeContext = config["configurable"]["runtime"]
    if runtime.is_cancelled(state["workflow_id"]):
        return {"cancelled": True, "status": "cancelled"}

    result = await CriticAgent(runtime).run(dict(state))
    updates = _apply_agent_result(state, result)
    critic_output = result.output
    updates["needs_retry"] = critic_output.get("needs_retry", False)
    updates["human_review_required"] = critic_output.get("human_review_required", False)
    if critic_output.get("human_review_required"):
        updates["status"] = "awaiting_human_review"
    return updates


async def _finalize_node(state: WorkflowGraphState, config) -> dict[str, Any]:
    brief = (state.get("agent_outputs") or {}).get("executive_brief", {})
    return {
        "status": "completed",
        "final_output": {
            "title": brief.get("title"),
            "summary": brief.get("summary"),
            "key_points": brief.get("key_points", []),
            "confidence": state.get("confidence", 0.0),
            "citations": state.get("citations", []),
        },
    }


def _apply_agent_result(
    state: WorkflowGraphState,
    result: AgentResult,
    *,
    plan: list[str] | None = None,
) -> dict[str, Any]:
    completed_steps = list(state.get("completed_steps") or [])
    if result.agent not in completed_steps:
        completed_steps.append(result.agent)

    agent_outputs = dict(state.get("agent_outputs") or {})
    agent_outputs[result.agent] = result.output

    citations = merge_citations(
        list(state.get("citations") or []),
        result.citations,
    )

    trace = list(state.get("trace") or [])
    trace.append(
        {
            "agent": result.agent,
            "event_type": "agent_completed" if result.success else "agent_failed",
            "message": result.error or f"{result.agent} completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "confidence": result.confidence,
            "tool_calls": result.metadata.tool_calls,
            "latency_ms": result.metadata.latency_ms,
            "retrieval_statistics": result.metadata.retrieval_statistics,
        }
    )

    bind_context(workflow_id=state.get("workflow_id"), agent=result.agent)
    logger.info(
        "workflow.agent.completed",
        agent=result.agent,
        confidence=result.confidence,
        latency_ms=result.metadata.latency_ms,
        tool_calls=result.metadata.tool_calls,
        retrieval_statistics=result.metadata.retrieval_statistics,
    )

    updates: dict[str, Any] = {
        "completed_steps": completed_steps,
        "agent_outputs": agent_outputs,
        "citations": citations,
        "confidence": max(float(state.get("confidence") or 0.0), result.confidence),
        "trace": trace,
        "status": "running",
    }
    if plan is not None:
        updates["plan"] = plan
    if not result.success and result.error:
        failed_steps = list(state.get("failed_steps") or [])
        if result.agent not in failed_steps:
            failed_steps.append(result.agent)
        updates["failed_steps"] = failed_steps
        errors = list(state.get("errors") or [])
        errors.append(result.error)
        updates["errors"] = errors
    return updates


def _route_after_planner(state: WorkflowGraphState) -> str:
    if state.get("cancelled"):
        return "finalize"
    return _next_executable_agent(state) or "critic"


def _route_after_agent(state: WorkflowGraphState) -> str:
    if state.get("cancelled") or state.get("status") == "failed":
        return "finalize"
    return _next_executable_agent(state) or "critic"


def _route_after_critic(state: WorkflowGraphState) -> str:
    if state.get("cancelled"):
        return "finalize"
    if state.get("needs_retry") and int(state.get("retry_count") or 0) < int(state.get("max_retries") or 2):
        return "document_discovery"
    if state.get("human_review_required"):
        return "finalize"
    return "finalize"


def _next_executable_agent(state: WorkflowGraphState) -> str | None:
    plan = state.get("plan") or []
    completed = set(state.get("completed_steps") or [])
    for agent in plan:
        if agent in EXECUTABLE_AGENTS and agent not in completed:
            return agent
    return None


def _log_agent_failure(state: WorkflowGraphState, agent_name: str, exc: Exception) -> None:
    logger.warning(
        "workflow.agent.failed",
        workflow_id=state.get("workflow_id"),
        agent=agent_name,
        error=str(exc),
    )

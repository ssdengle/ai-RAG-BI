from __future__ import annotations

from datetime import datetime, timezone

from apps.api.app.agents.runtime import WorkflowRuntimeContext
from apps.api.app.core.logging import bind_context, get_logger
from apps.api.app.domain.workflows import WorkflowRun, WorkflowStatus, WorkflowTraceEvent
from apps.api.app.repositories.workflow_repository import WorkflowRepository
from apps.api.app.workflows.graph import build_workflow_graph
from apps.api.app.workflows.state import WorkflowGraphState


class WorkflowOrchestrator:
    """Runs LangGraph workflows and persists state after each step."""

    def __init__(self, *, workflow_repository: WorkflowRepository) -> None:
        self._workflow_repository = workflow_repository
        self._graph = build_workflow_graph()
        self._logger = get_logger("api.workflow.orchestrator")

    async def run(
        self,
        runtime: WorkflowRuntimeContext,
        workflow: WorkflowRun,
    ) -> WorkflowRun:
        bind_context(workflow_id=workflow.workflow_id)
        workflow.status = WorkflowStatus.RUNNING
        workflow.started_at = workflow.started_at or datetime.now(timezone.utc)
        await self._workflow_repository.save_workflow(runtime.session, workflow)
        await runtime.session.commit()

        initial_state = self._workflow_to_graph_state(workflow)
        config = {"configurable": {"runtime": runtime}}

        try:
            async for event in self._graph.astream(initial_state, config=config):
                node_name = next(iter(event.keys()))
                state_update = event[node_name]
                needs_retry_restart = (
                    node_name == "document_discovery" and workflow.state.get("needs_retry")
                )
                workflow = self._merge_graph_state(workflow, state_update)

                if needs_retry_restart:
                    workflow.retry_count += 1
                    workflow.state["needs_retry"] = False
                    workflow.completed_steps = ["planner"]
                    workflow.state["completed_steps"] = ["planner"]

                if runtime.is_cancelled(workflow.workflow_id):
                    workflow.status = WorkflowStatus.CANCELLED
                    workflow.completed_at = datetime.now(timezone.utc)
                    break

                if workflow.status == WorkflowStatus.FAILED:
                    workflow.completed_at = datetime.now(timezone.utc)
                    break

                if node_name == "finalize":
                    if workflow.human_review_required:
                        workflow.status = WorkflowStatus.AWAITING_HUMAN_REVIEW
                    elif workflow.status != WorkflowStatus.CANCELLED:
                        workflow.status = WorkflowStatus.COMPLETED
                    workflow.completed_at = datetime.now(timezone.utc)

                await self._workflow_repository.save_workflow(runtime.session, workflow)
                await runtime.session.commit()
                self._logger.info(
                    "workflow.step.completed",
                    workflow_id=workflow.workflow_id,
                    step=node_name,
                    status=workflow.status.value,
                    confidence=workflow.confidence,
                )
        except Exception as exc:
            workflow.status = WorkflowStatus.FAILED
            workflow.errors.append(str(exc))
            workflow.completed_at = datetime.now(timezone.utc)
            await self._workflow_repository.save_workflow(runtime.session, workflow)
            await runtime.session.commit()
            self._logger.exception("workflow.run.failed", workflow_id=workflow.workflow_id)
            raise

        return workflow

    @staticmethod
    def _workflow_to_graph_state(workflow: WorkflowRun) -> WorkflowGraphState:
        state = dict(workflow.state)
        state.update(
            {
                "workflow_id": workflow.workflow_id,
                "user_request": workflow.user_request,
                "company_id": workflow.company_id,
                "company_ids": workflow.company_ids,
                "topic": workflow.topic,
                "plan": workflow.plan,
                "completed_steps": workflow.completed_steps,
                "failed_steps": workflow.failed_steps,
                "confidence": workflow.confidence,
                "human_review_required": workflow.human_review_required,
                "retry_count": workflow.retry_count,
                "max_retries": workflow.max_retries,
                "errors": workflow.errors,
                "final_output": workflow.final_output,
                "trace": [
                    {
                        "agent": event.agent,
                        "event_type": event.event_type,
                        "message": event.message,
                        "timestamp": event.timestamp.isoformat(),
                        "confidence": event.confidence,
                        "tool_calls": event.tool_calls,
                        "latency_ms": event.latency_ms,
                        "retrieval_statistics": event.retrieval_statistics,
                    }
                    for event in workflow.trace
                ],
            }
        )
        return state  # type: ignore[return-value]

    @staticmethod
    def _merge_graph_state(workflow: WorkflowRun, update: dict) -> WorkflowRun:
        workflow.state.update(update)
        workflow.plan = list(update.get("plan") or workflow.plan)
        workflow.completed_steps = list(update.get("completed_steps") or workflow.completed_steps)
        workflow.failed_steps = list(update.get("failed_steps") or workflow.failed_steps)
        workflow.confidence = float(update.get("confidence", workflow.confidence))
        workflow.human_review_required = bool(
            update.get("human_review_required", workflow.human_review_required)
        )
        workflow.errors = list(update.get("errors") or workflow.errors)
        workflow.final_output = update.get("final_output", workflow.final_output)
        if "status" in update:
            try:
                workflow.status = WorkflowStatus(str(update["status"]))
            except ValueError:
                pass
        trace_items = update.get("trace")
        if trace_items:
            workflow.trace = [
                WorkflowTraceEvent(
                    agent=item["agent"],
                    event_type=item["event_type"],
                    message=item["message"],
                    timestamp=datetime.fromisoformat(item["timestamp"]),
                    confidence=item.get("confidence"),
                    tool_calls=list(item.get("tool_calls") or []),
                    latency_ms=item.get("latency_ms"),
                    retrieval_statistics=dict(item.get("retrieval_statistics") or {}),
                )
                for item in trace_items
            ]
        workflow.updated_at = datetime.now(timezone.utc)
        return workflow

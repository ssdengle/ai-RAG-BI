from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.domain.workflows import WorkflowRun, WorkflowStatus, WorkflowTraceEvent
from apps.api.app.repositories.models import WorkflowRunModel


class WorkflowRepository:
    async def create_workflow(
        self,
        session: AsyncSession,
        *,
        user_request: str,
        topic: str,
        company_id: str | None = None,
        company_ids: list[str] | None = None,
        max_retries: int = 2,
    ) -> WorkflowRun:
        now = datetime.now(timezone.utc)
        workflow_id = str(uuid4())
        initial_state = {
            "workflow_id": workflow_id,
            "user_request": user_request,
            "company_id": company_id,
            "company_ids": company_ids or ([company_id] if company_id else []),
            "topic": topic,
            "plan": [],
            "completed_steps": [],
            "failed_steps": [],
            "agent_outputs": {},
            "citations": [],
            "confidence": 0.0,
            "human_review_required": False,
            "retry_count": 0,
            "max_retries": max_retries,
            "errors": [],
            "final_output": None,
            "cancelled": False,
            "needs_retry": False,
        }
        model = WorkflowRunModel(
            workflow_id=workflow_id,
            status=WorkflowStatus.PENDING.value,
            user_request=user_request,
            company_id=company_id,
            topic=topic,
            plan=[],
            completed_steps=[],
            failed_steps=[],
            state_json=initial_state,
            trace_json=[],
            confidence=0.0,
            human_review_required=False,
            retry_count=0,
            max_retries=max_retries,
            final_output=None,
            errors=[],
            started_at=None,
            completed_at=None,
        )
        session.add(model)
        await session.flush()
        await session.refresh(model)
        return self._to_workflow_run(model)

    async def get_workflow(self, session: AsyncSession, workflow_id: str) -> WorkflowRun | None:
        model = await session.get(WorkflowRunModel, workflow_id)
        if model is None:
            return None
        return self._to_workflow_run(model)

    async def save_workflow(self, session: AsyncSession, workflow: WorkflowRun) -> WorkflowRun:
        model = await session.get(WorkflowRunModel, workflow.workflow_id)
        if model is None:
            raise KeyError(workflow.workflow_id)

        model.status = workflow.status.value
        model.plan = workflow.plan
        model.completed_steps = workflow.completed_steps
        model.failed_steps = workflow.failed_steps
        model.state_json = workflow.state
        model.trace_json = [_trace_to_dict(event) for event in workflow.trace]
        model.confidence = workflow.confidence
        model.human_review_required = workflow.human_review_required
        model.retry_count = workflow.retry_count
        model.max_retries = workflow.max_retries
        model.final_output = workflow.final_output
        model.errors = workflow.errors
        model.started_at = workflow.started_at
        model.completed_at = workflow.completed_at
        await session.flush()
        await session.refresh(model)
        return self._to_workflow_run(model)

    @staticmethod
    def _to_workflow_run(model: WorkflowRunModel) -> WorkflowRun:
        return WorkflowRun(
            workflow_id=model.workflow_id,
            status=WorkflowStatus(model.status),
            user_request=model.user_request,
            company_id=model.company_id,
            company_ids=model.state_json.get("company_ids", []),
            topic=model.topic,
            plan=list(model.plan or []),
            completed_steps=list(model.completed_steps or []),
            failed_steps=list(model.failed_steps or []),
            state=dict(model.state_json or {}),
            trace=[_trace_from_dict(item) for item in (model.trace_json or [])],
            confidence=float(model.confidence),
            human_review_required=bool(model.human_review_required),
            retry_count=int(model.retry_count),
            max_retries=int(model.max_retries),
            final_output=model.final_output,
            errors=list(model.errors or []),
            created_at=model.created_at,
            updated_at=model.updated_at,
            started_at=model.started_at,
            completed_at=model.completed_at,
        )


def _trace_to_dict(event: WorkflowTraceEvent) -> dict[str, Any]:
    return {
        "agent": event.agent,
        "event_type": event.event_type,
        "message": event.message,
        "timestamp": event.timestamp.isoformat(),
        "confidence": event.confidence,
        "tool_calls": event.tool_calls,
        "latency_ms": event.latency_ms,
        "retrieval_statistics": event.retrieval_statistics,
    }


def _trace_from_dict(payload: dict[str, Any]) -> WorkflowTraceEvent:
    return WorkflowTraceEvent(
        agent=str(payload.get("agent", "")),
        event_type=str(payload.get("event_type", "")),
        message=str(payload.get("message", "")),
        timestamp=datetime.fromisoformat(str(payload["timestamp"])),
        confidence=payload.get("confidence"),
        tool_calls=list(payload.get("tool_calls") or []),
        latency_ms=payload.get("latency_ms"),
        retrieval_statistics=dict(payload.get("retrieval_statistics") or {}),
    )

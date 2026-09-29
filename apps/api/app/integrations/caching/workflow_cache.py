from __future__ import annotations

from typing import Any

from apps.api.app.core.cache import CacheClient, build_cache_key
from apps.api.app.core.metrics import record_cache_hit, record_cache_miss
from apps.api.app.core.config import CacheSettings
from apps.api.app.domain.workflows import WorkflowRun
from apps.api.app.services.workflow_service import WorkflowService


class CachingWorkflowService:
    """Caches completed workflow runs keyed by request fingerprint."""

    def __init__(self, inner: WorkflowService, cache: CacheClient, settings: CacheSettings) -> None:
        self._inner = inner
        self._cache = cache
        self._settings = settings

    async def run_workflow(
        self,
        session,
        *,
        user_request: str,
        topic: str,
        company_id: str | None = None,
        company_ids: list[str] | None = None,
        max_retries: int = 2,
    ) -> WorkflowRun:
        cache_key = build_cache_key(
            "workflow",
            {
                "user_request": user_request,
                "topic": topic,
                "company_id": company_id,
                "company_ids": company_ids or [],
                "max_retries": max_retries,
            },
        )
        cached = await self._cache.get_json(cache_key)
        if cached is not None:
            record_cache_hit("workflow")
            return _workflow_from_dict(cached)
        record_cache_miss("workflow")

        result = await self._inner.run_workflow(
            session,
            user_request=user_request,
            topic=topic,
            company_id=company_id,
            company_ids=company_ids,
            max_retries=max_retries,
        )
        await self._cache.set_json(cache_key, _workflow_to_dict(result), ttl_seconds=self._settings.workflow_ttl_seconds)
        return result

    async def get_workflow(self, session, *, workflow_id: str) -> WorkflowRun:
        return await self._inner.get_workflow(session, workflow_id=workflow_id)

    async def get_workflow_state(self, session, *, workflow_id: str) -> dict:
        return await self._inner.get_workflow_state(session, workflow_id=workflow_id)

    async def get_workflow_trace(self, session, *, workflow_id: str) -> list[dict]:
        return await self._inner.get_workflow_trace(session, workflow_id=workflow_id)

    async def retry_workflow(self, session, *, workflow_id: str) -> WorkflowRun:
        return await self._inner.retry_workflow(session, workflow_id=workflow_id)

    async def cancel_workflow(self, session, *, workflow_id: str) -> WorkflowRun:
        return await self._inner.cancel_workflow(session, workflow_id=workflow_id)


def _workflow_to_dict(workflow: WorkflowRun) -> dict[str, Any]:
    return {
        "workflow_id": workflow.workflow_id,
        "status": workflow.status.value,
        "user_request": workflow.user_request,
        "company_id": workflow.company_id,
        "company_ids": workflow.company_ids,
        "topic": workflow.topic,
        "plan": workflow.plan,
        "completed_steps": workflow.completed_steps,
        "failed_steps": workflow.failed_steps,
        "state": workflow.state,
        "trace": [event.__dict__ for event in workflow.trace],
        "confidence": workflow.confidence,
        "human_review_required": workflow.human_review_required,
        "retry_count": workflow.retry_count,
        "max_retries": workflow.max_retries,
        "final_output": workflow.final_output,
        "errors": workflow.errors,
        "created_at": workflow.created_at.isoformat() if workflow.created_at else None,
        "updated_at": workflow.updated_at.isoformat() if workflow.updated_at else None,
        "started_at": workflow.started_at.isoformat() if workflow.started_at else None,
        "completed_at": workflow.completed_at.isoformat() if workflow.completed_at else None,
    }


def _workflow_from_dict(payload: dict[str, Any]) -> WorkflowRun:
    from datetime import datetime

    from apps.api.app.domain.workflows import WorkflowStatus, WorkflowTraceEvent

    def _parse_dt(value: str | None):
        return datetime.fromisoformat(value) if value else None

    return WorkflowRun(
        workflow_id=payload["workflow_id"],
        status=WorkflowStatus(payload["status"]),
        user_request=payload["user_request"],
        company_id=payload.get("company_id"),
        company_ids=list(payload.get("company_ids") or []),
        topic=payload["topic"],
        plan=list(payload.get("plan") or []),
        completed_steps=list(payload.get("completed_steps") or []),
        failed_steps=list(payload.get("failed_steps") or []),
        state=dict(payload.get("state") or {}),
        trace=[WorkflowTraceEvent(**event) for event in payload.get("trace", [])],
        confidence=float(payload.get("confidence", 0.0)),
        human_review_required=bool(payload.get("human_review_required", False)),
        retry_count=int(payload.get("retry_count", 0)),
        max_retries=int(payload.get("max_retries", 2)),
        final_output=payload.get("final_output"),
        errors=list(payload.get("errors") or []),
        created_at=_parse_dt(payload.get("created_at")),
        updated_at=_parse_dt(payload.get("updated_at")),
        started_at=_parse_dt(payload.get("started_at")),
        completed_at=_parse_dt(payload.get("completed_at")),
    )

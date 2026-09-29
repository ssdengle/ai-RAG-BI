from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.agents.runtime import WorkflowRuntimeContext
from apps.api.app.core.errors import DomainError
from apps.api.app.core.logging import get_logger
from apps.api.app.domain.workflows import WorkflowRun, WorkflowStatus
from apps.api.app.repositories.workflow_repository import WorkflowRepository
from apps.api.app.workflows.orchestrator import WorkflowOrchestrator


class WorkflowService:
    def __init__(
        self,
        *,
        workflow_repository: WorkflowRepository,
        orchestrator: WorkflowOrchestrator,
        runtime_factory,
    ) -> None:
        self._workflow_repository = workflow_repository
        self._orchestrator = orchestrator
        self._runtime_factory = runtime_factory
        self._logger = get_logger("api.workflow_service")

    async def run_workflow(
        self,
        session: AsyncSession,
        *,
        user_request: str,
        topic: str,
        company_id: str | None = None,
        company_ids: list[str] | None = None,
        max_retries: int = 2,
    ) -> WorkflowRun:
        workflow = await self._workflow_repository.create_workflow(
            session,
            user_request=user_request,
            topic=topic,
            company_id=company_id,
            company_ids=company_ids,
            max_retries=max_retries,
        )
        await session.commit()

        runtime = self._runtime_factory(session)
        workflow = await self._orchestrator.run(runtime, workflow)
        self._logger.info(
            "workflow.run.completed",
            workflow_id=workflow.workflow_id,
            status=workflow.status.value,
            confidence=workflow.confidence,
        )
        return workflow

    async def get_workflow(self, session: AsyncSession, *, workflow_id: str) -> WorkflowRun:
        workflow = await self._workflow_repository.get_workflow(session, workflow_id)
        if workflow is None:
            raise DomainError(
                "Workflow was not found.",
                details=workflow_id,
                code="workflow_not_found",
                status_code=404,
            )
        return workflow

    async def get_workflow_state(self, session: AsyncSession, *, workflow_id: str) -> dict:
        workflow = await self.get_workflow(session, workflow_id=workflow_id)
        return workflow.state

    async def get_workflow_trace(self, session: AsyncSession, *, workflow_id: str) -> list[dict]:
        workflow = await self.get_workflow(session, workflow_id=workflow_id)
        return [
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
        ]

    async def retry_workflow(self, session: AsyncSession, *, workflow_id: str) -> WorkflowRun:
        workflow = await self.get_workflow(session, workflow_id=workflow_id)
        if workflow.status not in {
            WorkflowStatus.FAILED,
            WorkflowStatus.AWAITING_HUMAN_REVIEW,
            WorkflowStatus.COMPLETED,
        }:
            raise DomainError(
                "Workflow cannot be retried in its current status.",
                details=workflow.status.value,
                code="workflow_retry_not_allowed",
                status_code=409,
            )

        workflow.status = WorkflowStatus.PENDING
        workflow.retry_count += 1
        workflow.failed_steps = []
        workflow.errors = []
        workflow.completed_steps = [step for step in workflow.completed_steps if step == "planner"]
        workflow.state["needs_retry"] = False
        workflow.state["completed_steps"] = workflow.completed_steps
        workflow.human_review_required = False
        workflow.completed_at = None
        await self._workflow_repository.save_workflow(session, workflow)
        await session.commit()

        runtime = self._runtime_factory(session)
        return await self._orchestrator.run(runtime, workflow)

    async def cancel_workflow(self, session: AsyncSession, *, workflow_id: str) -> WorkflowRun:
        workflow = await self.get_workflow(session, workflow_id=workflow_id)
        if workflow.status in {WorkflowStatus.COMPLETED, WorkflowStatus.CANCELLED}:
            raise DomainError(
                "Workflow cannot be cancelled in its current status.",
                details=workflow.status.value,
                code="workflow_cancel_not_allowed",
                status_code=409,
            )

        runtime = self._runtime_factory(session)
        runtime.mark_cancelled(workflow_id)
        workflow.status = WorkflowStatus.CANCELLED
        workflow.state["cancelled"] = True
        workflow.completed_at = datetime.now(timezone.utc)
        await self._workflow_repository.save_workflow(session, workflow)
        await session.commit()
        self._logger.info("workflow.cancelled", workflow_id=workflow_id)
        return workflow

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from apps.api.app.core.errors import DomainError
from apps.api.app.domain.workflows import WorkflowRun, WorkflowStatus, WorkflowTraceEvent
from apps.api.app.services.workflow_service import WorkflowService
from apps.api.tests.unit.test_workflow_agents import _FakeSession, build_fake_runtime


NOW = datetime.now(timezone.utc)


class _FakeWorkflowRepository:
    def __init__(self) -> None:
        self.workflows: dict[str, WorkflowRun] = {}

    async def create_workflow(self, session, *, user_request, topic, company_id=None, company_ids=None, max_retries=2):
        workflow = WorkflowRun(
            workflow_id="wf-1",
            status=WorkflowStatus.PENDING,
            user_request=user_request,
            company_id=company_id,
            company_ids=company_ids or [],
            topic=topic,
            plan=[],
            completed_steps=[],
            failed_steps=[],
            state={"workflow_id": "wf-1", "needs_retry": False, "cancelled": False},
            trace=[],
            confidence=0.0,
            human_review_required=False,
            retry_count=0,
            max_retries=max_retries,
            final_output=None,
            errors=[],
            created_at=NOW,
            updated_at=NOW,
        )
        self.workflows[workflow.workflow_id] = workflow
        return workflow

    async def get_workflow(self, session, workflow_id):
        return self.workflows.get(workflow_id)

    async def save_workflow(self, session, workflow):
        self.workflows[workflow.workflow_id] = workflow
        return workflow


class _FakeOrchestrator:
    async def run(self, runtime, workflow):
        workflow.status = WorkflowStatus.COMPLETED
        workflow.completed_steps = ["planner", "document_discovery", "executive_brief", "critic"]
        workflow.plan = ["document_discovery", "executive_brief"]
        workflow.confidence = 0.91
        workflow.final_output = {"summary": "Completed brief"}
        workflow.completed_at = datetime.now(timezone.utc)
        workflow.trace = [
            WorkflowTraceEvent(
                agent="planner",
                event_type="agent_completed",
                message="planner completed",
                timestamp=NOW,
                confidence=0.95,
            )
        ]
        await runtime.session.commit()
        return workflow


def test_workflow_service_run_creates_and_executes_workflow() -> None:
    repository = _FakeWorkflowRepository()
    service = WorkflowService(
        workflow_repository=repository,
        orchestrator=_FakeOrchestrator(),
        runtime_factory=lambda session: build_fake_runtime(session=session),
    )

    workflow = asyncio.run(
        service.run_workflow(
            _FakeSession(),
            user_request="Summarize market trends and risks",
            topic="Market outlook",
            company_id="company-1",
        )
    )

    assert workflow.status == WorkflowStatus.COMPLETED
    assert workflow.final_output is not None


def test_workflow_service_cancel_marks_workflow_cancelled() -> None:
    repository = _FakeWorkflowRepository()
    workflow = asyncio.run(
        repository.create_workflow(
            _FakeSession(),
            user_request="test",
            topic="topic",
        )
    )
    workflow.status = WorkflowStatus.RUNNING
    repository.workflows[workflow.workflow_id] = workflow

    service = WorkflowService(
        workflow_repository=repository,
        orchestrator=_FakeOrchestrator(),
        runtime_factory=lambda session: build_fake_runtime(session=session),
    )

    cancelled = asyncio.run(service.cancel_workflow(_FakeSession(), workflow_id="wf-1"))

    assert cancelled.status == WorkflowStatus.CANCELLED


def test_workflow_service_retry_reruns_failed_workflow() -> None:
    repository = _FakeWorkflowRepository()
    workflow = asyncio.run(
        repository.create_workflow(
            _FakeSession(),
            user_request="test",
            topic="topic",
        )
    )
    workflow.status = WorkflowStatus.FAILED
    repository.workflows[workflow.workflow_id] = workflow

    service = WorkflowService(
        workflow_repository=repository,
        orchestrator=_FakeOrchestrator(),
        runtime_factory=lambda session: build_fake_runtime(session=session),
    )

    retried = asyncio.run(service.retry_workflow(_FakeSession(), workflow_id="wf-1"))

    assert retried.status == WorkflowStatus.COMPLETED
    assert retried.retry_count == 1


def test_workflow_service_get_missing_workflow_raises_not_found() -> None:
    service = WorkflowService(
        workflow_repository=_FakeWorkflowRepository(),
        orchestrator=_FakeOrchestrator(),
        runtime_factory=lambda session: build_fake_runtime(session=session),
    )

    with pytest.raises(DomainError) as exc_info:
        asyncio.run(service.get_workflow(_FakeSession(), workflow_id="missing"))

    assert exc_info.value.code == "workflow_not_found"

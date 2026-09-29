from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from apps.api.app.domain.workflows import WorkflowRun, WorkflowStatus
from apps.api.app.workflows.graph import build_workflow_graph
from apps.api.tests.unit.test_workflow_agents import _FakeSession, build_fake_runtime


NOW = datetime.now(timezone.utc)


class _InMemoryWorkflowRepository:
    def __init__(self) -> None:
        self.saved: list[WorkflowRun] = []

    async def save_workflow(self, session, workflow):
        self.saved.append(workflow)
        return workflow


class _RecordingOrchestrator:
    def __init__(self, repository):
        self._graph = build_workflow_graph()
        self._repository = repository

    async def run(self, runtime, workflow):
        from apps.api.app.workflows.orchestrator import WorkflowOrchestrator

        orchestrator = WorkflowOrchestrator(workflow_repository=self._repository)
        orchestrator._graph = self._graph
        return await orchestrator.run(runtime, workflow)


def test_langgraph_workflow_executes_planned_agents_and_persists_state() -> None:
    repository = _InMemoryWorkflowRepository()
    runtime = build_fake_runtime(session=_FakeSession())
    workflow = WorkflowRun(
        workflow_id="wf-graph-1",
        status=WorkflowStatus.PENDING,
        user_request="Summarize market trends and risks for Acme",
        company_id="company-1",
        company_ids=["company-1"],
        topic="Market outlook",
        plan=[],
        completed_steps=[],
        failed_steps=[],
        state={
            "workflow_id": "wf-graph-1",
            "needs_retry": False,
            "cancelled": False,
            "retry_count": 0,
            "max_retries": 2,
        },
        trace=[],
        confidence=0.0,
        human_review_required=False,
        retry_count=0,
        max_retries=2,
        final_output=None,
        errors=[],
        created_at=NOW,
        updated_at=NOW,
    )

    completed = asyncio.run(_RecordingOrchestrator(repository).run(runtime, workflow))

    assert "planner" in completed.completed_steps
    assert "document_discovery" in completed.completed_steps
    assert "executive_brief" in completed.completed_steps
    assert "critic" in completed.completed_steps
    assert completed.status in {WorkflowStatus.COMPLETED, WorkflowStatus.AWAITING_HUMAN_REVIEW}
    assert repository.saved

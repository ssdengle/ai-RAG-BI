from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from apps.api.app.api.workflows import get_workflow_service
from apps.api.app.core.database import get_db_session
from apps.api.app.domain.workflows import WorkflowRun, WorkflowStatus, WorkflowTraceEvent
from apps.api.app.main import create_app
from apps.api.tests.conftest import FakeDatabaseManager, FakeRedisManager, build_test_settings


NOW = datetime.now(timezone.utc)


class _FakeWorkflowService:
    def __init__(self) -> None:
        self.workflow = WorkflowRun(
            workflow_id="wf-1",
            status=WorkflowStatus.COMPLETED,
            user_request="Summarize market trends and risks",
            company_id="company-1",
            company_ids=["company-1"],
            topic="Market outlook",
            plan=["document_discovery", "market_intelligence", "risk_analysis", "executive_brief"],
            completed_steps=["planner", "document_discovery", "executive_brief", "critic"],
            failed_steps=[],
            state={
                "workflow_id": "wf-1",
                "citations": [
                    {
                        "document_id": "doc-1",
                        "title": "Annual Report",
                        "chunk_id": "chunk-1",
                        "page_number": 2,
                        "score": 0.91,
                        "snippet": "Revenue increased.",
                    }
                ],
            },
            trace=[
                WorkflowTraceEvent(
                    agent="document_discovery",
                    event_type="agent_completed",
                    message="document_discovery completed",
                    timestamp=NOW,
                    confidence=0.91,
                    tool_calls=["hybrid_retrieval"],
                    latency_ms=12.5,
                    retrieval_statistics={"returned_chunks": 1},
                )
            ],
            confidence=0.91,
            human_review_required=False,
            retry_count=0,
            max_retries=2,
            final_output={"summary": "Acme revenue increased."},
            errors=[],
            created_at=NOW,
            updated_at=NOW,
            started_at=NOW,
            completed_at=NOW,
        )

    async def run_workflow(self, session, *, user_request, topic, company_id=None, company_ids=None, max_retries=2):
        return self.workflow

    async def get_workflow(self, session, *, workflow_id):
        return self.workflow

    async def get_workflow_state(self, session, *, workflow_id):
        return self.workflow.state

    async def get_workflow_trace(self, session, *, workflow_id):
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
            for event in self.workflow.trace
        ]

    async def retry_workflow(self, session, *, workflow_id):
        self.workflow.retry_count += 1
        self.workflow.status = WorkflowStatus.COMPLETED
        return self.workflow

    async def cancel_workflow(self, session, *, workflow_id):
        self.workflow.status = WorkflowStatus.CANCELLED
        return self.workflow


async def _override_db_session():
    yield None


def _build_test_app():
    app = create_app(
        settings=build_test_settings(),
        database_manager=FakeDatabaseManager(),
        redis_manager=FakeRedisManager(),
        perform_startup_checks=False,
    )
    app.dependency_overrides[get_db_session] = _override_db_session
    app.dependency_overrides[get_workflow_service] = lambda: _FakeWorkflowService()
    return app


def test_run_workflow_endpoint() -> None:
    with TestClient(_build_test_app()) as client:
        response = client.post(
            "/v1/workflows/run",
            json={
                "user_request": "Summarize market trends and risks",
                "topic": "Market outlook",
                "company_id": "company-1",
            },
        )

    assert response.status_code == 201
    assert response.json()["workflow_id"] == "wf-1"
    assert response.json()["status"] == "completed"


def test_get_workflow_state_and_trace_endpoints() -> None:
    with TestClient(_build_test_app()) as client:
        state_response = client.get("/v1/workflows/wf-1/state")
        trace_response = client.get("/v1/workflows/wf-1/trace")

    assert state_response.status_code == 200
    assert state_response.json()["state"]["citations"]
    assert trace_response.status_code == 200
    assert trace_response.json()["trace"][0]["agent"] == "document_discovery"


def test_retry_and_cancel_workflow_endpoints() -> None:
    with TestClient(_build_test_app()) as client:
        retry_response = client.post("/v1/workflows/wf-1/retry")
        cancel_response = client.post("/v1/workflows/wf-1/cancel")

    assert retry_response.status_code == 200
    assert retry_response.json()["retry_count"] == 1
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"

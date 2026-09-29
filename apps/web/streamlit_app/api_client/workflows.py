from __future__ import annotations

from typing import Any, Optional

from apps.web.streamlit_app.api_client.base import BaseApiClient
from apps.web.streamlit_app.api_client.models import (
    WorkflowResponse,
    WorkflowStateResponse,
    WorkflowTraceResponse,
)


class WorkflowsApiClient:
    def __init__(self, client: BaseApiClient) -> None:
        self._client = client

    def run_workflow(
        self,
        *,
        user_request: str,
        topic: str,
        company_id: Optional[str] = None,
        company_ids: Optional[list[str]] = None,
        max_retries: int = 2,
    ) -> WorkflowResponse:
        payload: dict[str, Any] = {
            "user_request": user_request,
            "topic": topic,
            "max_retries": max_retries,
        }
        if company_id:
            payload["company_id"] = company_id
        if company_ids:
            payload["company_ids"] = company_ids
        data = self._client.post_json("/v1/workflows/run", json=payload)
        return WorkflowResponse.model_validate(data)

    def get_workflow(self, workflow_id: str) -> WorkflowResponse:
        data = self._client.get_json(f"/v1/workflows/{workflow_id}")
        return WorkflowResponse.model_validate(data)

    def get_state(self, workflow_id: str) -> WorkflowStateResponse:
        data = self._client.get_json(f"/v1/workflows/{workflow_id}/state")
        return WorkflowStateResponse.model_validate(data)

    def get_trace(self, workflow_id: str) -> WorkflowTraceResponse:
        data = self._client.get_json(f"/v1/workflows/{workflow_id}/trace")
        return WorkflowTraceResponse.model_validate(data)

    def retry_workflow(self, workflow_id: str) -> WorkflowResponse:
        data = self._client.post_json(f"/v1/workflows/{workflow_id}/retry")
        return WorkflowResponse.model_validate(data)

    def cancel_workflow(self, workflow_id: str) -> WorkflowResponse:
        data = self._client.post_json(f"/v1/workflows/{workflow_id}/cancel")
        return WorkflowResponse.model_validate(data)

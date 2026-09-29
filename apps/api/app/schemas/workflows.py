from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class RunWorkflowRequest(BaseModel):
    user_request: str = Field(..., min_length=1)
    topic: str = Field(..., min_length=1)
    company_id: Optional[str] = None
    company_ids: Optional[list[str]] = None
    max_retries: int = Field(default=2, ge=0, le=5)


class WorkflowTraceEventResponse(BaseModel):
    agent: str
    event_type: str
    message: str
    timestamp: datetime
    confidence: Optional[float]
    tool_calls: list[str]
    latency_ms: Optional[float]
    retrieval_statistics: dict[str, Any]


class WorkflowResponse(BaseModel):
    workflow_id: str
    status: str
    user_request: str
    topic: str
    company_id: Optional[str]
    company_ids: list[str]
    plan: list[str]
    completed_steps: list[str]
    failed_steps: list[str]
    confidence: float
    human_review_required: bool
    retry_count: int
    max_retries: int
    final_output: Optional[dict[str, Any]]
    errors: list[str]
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


class WorkflowStateResponse(BaseModel):
    workflow_id: str
    status: str
    state: dict[str, Any]


class WorkflowTraceResponse(BaseModel):
    workflow_id: str
    trace: list[WorkflowTraceEventResponse]

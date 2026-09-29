from __future__ import annotations

from typing import Any, Optional, TypedDict


class WorkflowGraphState(TypedDict, total=False):
    workflow_id: str
    user_request: str
    company_id: Optional[str]
    company_ids: list[str]
    topic: str
    status: str
    plan: list[str]
    completed_steps: list[str]
    failed_steps: list[str]
    agent_outputs: dict[str, Any]
    citations: list[dict[str, Any]]
    confidence: float
    human_review_required: bool
    retry_count: int
    max_retries: int
    errors: list[str]
    final_output: Optional[dict[str, Any]]
    cancelled: bool
    needs_retry: bool
    trace: list[dict[str, Any]]

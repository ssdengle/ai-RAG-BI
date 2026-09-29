from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from apps.api.app.domain.retrieval import Citation


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_HUMAN_REVIEW = "awaiting_human_review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


AgentName = Literal[
    "planner",
    "document_discovery",
    "market_intelligence",
    "competitor_intelligence",
    "risk_analysis",
    "executive_brief",
    "critic",
]


EXECUTABLE_AGENTS: tuple[str, ...] = (
    "document_discovery",
    "market_intelligence",
    "competitor_intelligence",
    "risk_analysis",
    "executive_brief",
)


@dataclass(frozen=True)
class AgentExecutionMetadata:
    latency_ms: float
    tool_calls: list[str] = field(default_factory=list)
    token_usage: Optional[dict[str, int]] = None
    retrieval_statistics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentResult:
    agent: str
    success: bool
    output: dict[str, Any]
    confidence: float
    citations: list[Citation]
    metadata: AgentExecutionMetadata
    error: Optional[str] = None


@dataclass(frozen=True)
class WorkflowTraceEvent:
    agent: str
    event_type: str
    message: str
    timestamp: datetime
    confidence: Optional[float] = None
    tool_calls: list[str] = field(default_factory=list)
    latency_ms: Optional[float] = None
    retrieval_statistics: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowRun:
    workflow_id: str
    status: WorkflowStatus
    user_request: str
    company_id: Optional[str]
    company_ids: list[str]
    topic: str
    plan: list[str]
    completed_steps: list[str]
    failed_steps: list[str]
    state: dict[str, Any]
    trace: list[WorkflowTraceEvent]
    confidence: float
    human_review_required: bool
    retry_count: int
    max_retries: int
    final_output: Optional[dict[str, Any]]
    errors: list[str]
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from apps.api.app.domain.retrieval import Citation, RetrievalMode


class EvaluationTargetType(str, Enum):
    RETRIEVAL = "retrieval"
    GROUNDED_QA = "grounded_qa"
    EXECUTIVE_BRIEF = "executive_brief"
    WORKFLOW = "workflow"


class EvaluationRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class FailureMode(str, Enum):
    LOW_ACCURACY = "low_accuracy"
    UNGROUNDED = "ungrounded"
    BAD_CITATIONS = "bad_citations"
    HALLUCINATION = "hallucination"
    INCOMPLETE = "incomplete"
    IRRELEVANT = "irrelevant"
    CONFIDENCE_MISCALIBRATION = "confidence_miscalibration"
    HIGH_LATENCY = "high_latency"
    HIGH_COST = "high_cost"
    SERVICE_ERROR = "service_error"
    EMPTY_RESPONSE = "empty_response"


ScorerName = Literal[
    "answer_accuracy",
    "groundedness",
    "citation_correctness",
    "hallucination_risk",
    "completeness",
    "relevance",
    "confidence_calibration",
    "latency",
    "cost",
]


DEFAULT_SCORERS: tuple[ScorerName, ...] = (
    "answer_accuracy",
    "groundedness",
    "citation_correctness",
    "hallucination_risk",
    "completeness",
    "relevance",
    "confidence_calibration",
    "latency",
    "cost",
)


@dataclass(frozen=True)
class SourceDocument:
    document_id: str
    title: Optional[str] = None
    chunk_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ExpectedAnswer:
    text: str
    required_citations: list[str] = field(default_factory=list)
    required_keywords: list[str] = field(default_factory=list)
    min_confidence: Optional[float] = None


@dataclass(frozen=True)
class ScoringRubric:
    pass_threshold: float = 0.7
    scorer_weights: dict[str, float] = field(default_factory=dict)
    scorer_thresholds: dict[str, float] = field(default_factory=dict)
    enabled_scorers: list[str] = field(default_factory=lambda: list(DEFAULT_SCORERS))


@dataclass(frozen=True)
class BenchmarkDataset:
    dataset_id: str
    name: str
    description: str
    target_type: EvaluationTargetType
    version: str
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class EvaluationTestCase:
    test_case_id: str
    dataset_id: str
    name: str
    query: str
    input_payload: dict[str, Any]
    expected_answer: ExpectedAnswer
    source_documents: list[SourceDocument]
    rubric: ScoringRubric
    tags: list[str]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ScorerResult:
    scorer: str
    score: float
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvaluationRun:
    run_id: str
    dataset_id: str
    status: EvaluationRunStatus
    target_type: EvaluationTargetType
    config: dict[str, Any]
    baseline_run_id: Optional[str]
    llm_provider: Optional[str]
    llm_model: Optional[str]
    summary: dict[str, Any]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


@dataclass(frozen=True)
class EvaluationResult:
    result_id: str
    run_id: str
    test_case_id: str
    test_case_name: str
    passed: bool
    overall_score: float
    scorer_results: list[ScorerResult]
    failure_modes: list[FailureMode]
    actual_output: dict[str, Any]
    latency_ms: Optional[float]
    token_usage: dict[str, Any]
    error_message: Optional[str]
    created_at: datetime


@dataclass(frozen=True)
class FailedTestCaseSummary:
    test_case_id: str
    test_case_name: str
    overall_score: float
    failure_modes: list[str]
    error_message: Optional[str]


@dataclass(frozen=True)
class ModelComparisonField:
    provider: Optional[str]
    model: Optional[str]
    average_score: float
    pass_rate: float
    total_test_cases: int


@dataclass(frozen=True)
class RegressionComparisonField:
    baseline_run_id: Optional[str]
    current_average_score: float
    baseline_average_score: Optional[float]
    score_delta: Optional[float]
    pass_rate_delta: Optional[float]
    regressed_test_cases: list[str]


@dataclass(frozen=True)
class EvaluationReport:
    run_id: str
    dataset_id: str
    dataset_name: str
    target_type: EvaluationTargetType
    status: EvaluationRunStatus
    passed: bool
    average_score: float
    pass_rate: float
    total_test_cases: int
    passed_test_cases: int
    failed_test_cases: list[FailedTestCaseSummary]
    failure_mode_summary: dict[str, int]
    model_comparison: ModelComparisonField
    regression_comparison: RegressionComparisonField
    scorer_averages: dict[str, float]
    created_at: datetime
    completed_at: Optional[datetime]


@dataclass(frozen=True)
class EvaluationExecutionContext:
    """Captured output from a target service invocation for scoring."""

    answer: str
    citations: list[Citation]
    confidence: Optional[float]
    retrieved_chunk_ids: list[str]
    latency_ms: float
    llm_provider: Optional[str]
    llm_model: Optional[str]
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    total_cost_usd: Optional[float]
    raw_output: dict[str, Any]
    error_message: Optional[str] = None


@dataclass(frozen=True)
class RunEvaluationConfig:
    mode: RetrievalMode = "hybrid"
    top_k: int = 5
    pass_threshold: float = 0.7
    enabled_scorers: list[str] = field(default_factory=lambda: list(DEFAULT_SCORERS))
    latency_threshold_ms: float = 30_000.0
    cost_threshold_usd: Optional[float] = None
    company_id: Optional[str] = None
    max_retries: int = 2

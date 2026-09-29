from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class CreateBenchmarkDatasetRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    target_type: str = Field(..., pattern="^(retrieval|grounded_qa|executive_brief|workflow)$")
    version: str = "1.0"
    metadata: dict[str, Any] = Field(default_factory=dict)


class BenchmarkDatasetResponse(BaseModel):
    dataset_id: str
    name: str
    description: str
    target_type: str
    version: str
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ExpectedAnswerRequest(BaseModel):
    text: str
    required_citations: list[str] = Field(default_factory=list)
    required_keywords: list[str] = Field(default_factory=list)
    min_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class SourceDocumentRequest(BaseModel):
    document_id: str
    title: Optional[str] = None
    chunk_ids: list[str] = Field(default_factory=list)


class ScoringRubricRequest(BaseModel):
    pass_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    scorer_weights: dict[str, float] = Field(default_factory=dict)
    scorer_thresholds: dict[str, float] = Field(default_factory=dict)
    enabled_scorers: list[str] = Field(default_factory=list)


class CreateTestCaseRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    query: str = Field(..., min_length=1)
    expected_answer: ExpectedAnswerRequest
    source_documents: list[SourceDocumentRequest] = Field(default_factory=list)
    rubric: ScoringRubricRequest = Field(default_factory=ScoringRubricRequest)
    input_payload: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class TestCaseResponse(BaseModel):
    test_case_id: str
    dataset_id: str
    name: str
    query: str
    expected_answer: ExpectedAnswerRequest
    source_documents: list[SourceDocumentRequest]
    rubric: ScoringRubricRequest
    input_payload: dict[str, Any]
    tags: list[str]
    created_at: datetime
    updated_at: datetime


class RunEvaluationRequest(BaseModel):
    pass_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    mode: str = Field(default="hybrid", pattern="^(semantic|keyword|hybrid)$")
    top_k: int = Field(default=5, ge=1, le=50)
    enabled_scorers: list[str] = Field(default_factory=list)
    latency_threshold_ms: float = Field(default=30000.0, ge=1.0)
    cost_threshold_usd: Optional[float] = Field(default=None, ge=0.0)
    company_id: Optional[str] = None
    max_retries: int = Field(default=2, ge=0, le=5)
    baseline_run_id: Optional[str] = None


class EvaluationRunResponse(BaseModel):
    run_id: str
    dataset_id: str
    status: str
    target_type: str
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


class ScorerResultResponse(BaseModel):
    scorer: str
    score: float
    passed: bool
    details: dict[str, Any]


class EvaluationResultResponse(BaseModel):
    result_id: str
    run_id: str
    test_case_id: str
    test_case_name: str
    passed: bool
    overall_score: float
    scorer_results: list[ScorerResultResponse]
    failure_modes: list[str]
    actual_output: dict[str, Any]
    latency_ms: Optional[float]
    token_usage: dict[str, Any]
    error_message: Optional[str]
    created_at: datetime


class FailedTestCaseResponse(BaseModel):
    test_case_id: str
    test_case_name: str
    overall_score: float
    failure_modes: list[str]
    error_message: Optional[str]


class ModelComparisonResponse(BaseModel):
    provider: Optional[str]
    model: Optional[str]
    average_score: float
    pass_rate: float
    total_test_cases: int


class RegressionComparisonResponse(BaseModel):
    baseline_run_id: Optional[str]
    current_average_score: float
    baseline_average_score: Optional[float]
    score_delta: Optional[float]
    pass_rate_delta: Optional[float]
    regressed_test_cases: list[str]


class EvaluationReportResponse(BaseModel):
    run_id: str
    dataset_id: str
    dataset_name: str
    target_type: str
    status: str
    passed: bool
    average_score: float
    pass_rate: float
    total_test_cases: int
    passed_test_cases: int
    failed_test_cases: list[FailedTestCaseResponse]
    failure_mode_summary: dict[str, int]
    model_comparison: ModelComparisonResponse
    regression_comparison: RegressionComparisonResponse
    scorer_averages: dict[str, float]
    created_at: datetime
    completed_at: Optional[datetime]

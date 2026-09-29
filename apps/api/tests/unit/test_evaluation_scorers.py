from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from apps.api.app.domain.evaluation import (
    EvaluationExecutionContext,
    EvaluationTestCase,
    ExpectedAnswer,
    RunEvaluationConfig,
    ScoringRubric,
)
from apps.api.app.domain.retrieval import Citation
from apps.api.app.evaluation.judge import HeuristicEvaluationJudge
from apps.api.app.evaluation.scorers import ScorerContext, build_default_scorer_registry


NOW = datetime.now(timezone.utc)


def _build_test_case(**overrides) -> EvaluationTestCase:
    defaults = {
        "test_case_id": "tc-1",
        "dataset_id": "ds-1",
        "name": "Revenue case",
        "query": "What happened to revenue?",
        "input_payload": {},
        "expected_answer": ExpectedAnswer(
            text="Revenue increased steadily.",
            required_citations=["chunk-1"],
            required_keywords=["revenue"],
            min_confidence=0.7,
        ),
        "source_documents": [],
        "rubric": ScoringRubric(pass_threshold=0.7),
        "tags": [],
        "created_at": NOW,
        "updated_at": NOW,
    }
    defaults.update(overrides)
    return EvaluationTestCase(**defaults)


def _build_execution(**overrides) -> EvaluationExecutionContext:
    defaults = {
        "answer": "Revenue increased steadily in all regions.",
        "citations": [
            Citation(
                document_id="doc-1",
                title="Annual Report",
                chunk_id="chunk-1",
                page_number=2,
                score=0.9,
                snippet="Revenue increased steadily in Q1.",
            )
        ],
        "confidence": 0.85,
        "retrieved_chunk_ids": ["chunk-1"],
        "latency_ms": 120.0,
        "llm_provider": "openai",
        "llm_model": "gpt-4o-mini",
        "prompt_tokens": 100,
        "completion_tokens": 40,
        "total_cost_usd": 0.001,
        "raw_output": {},
    }
    defaults.update(overrides)
    return EvaluationExecutionContext(**defaults)


def _score(scorer_name: str, test_case: EvaluationTestCase, execution: EvaluationExecutionContext):
    registry = build_default_scorer_registry(HeuristicEvaluationJudge())
    scorer = registry.get(scorer_name)
    assert scorer is not None
    context = ScorerContext(
        test_case=test_case,
        execution=execution,
        config=RunEvaluationConfig(),
        context_text="Revenue increased steadily in Q1.",
    )
    return asyncio.run(scorer.score(context))


def test_answer_accuracy_scorer_passes_matching_answer() -> None:
    result = _score("answer_accuracy", _build_test_case(), _build_execution())
    assert result.scorer == "answer_accuracy"
    assert result.score > 0.5
    assert result.score >= 0.6


def test_citation_correctness_scorer_requires_expected_citations() -> None:
    passing = _score("citation_correctness", _build_test_case(), _build_execution())
    failing = _score(
        "citation_correctness",
        _build_test_case(),
        _build_execution(citations=[]),
    )
    assert passing.passed is True
    assert failing.passed is False


def test_hallucination_risk_scorer_penalizes_unsupported_tokens() -> None:
    grounded = _score("groundedness", _build_test_case(), _build_execution())
    risky = _score(
        "hallucination_risk",
        _build_test_case(),
        _build_execution(answer="Quantum blockchain synergy transformed margins."),
    )
    assert grounded.score > 0.5
    assert risky.score < grounded.score


def test_latency_scorer_passes_within_threshold() -> None:
    result = _score("latency", _build_test_case(), _build_execution(latency_ms=500.0))
    assert result.passed is True


def test_latency_scorer_fails_when_over_threshold() -> None:
    result = _score(
        "latency",
        _build_test_case(),
        _build_execution(latency_ms=60_000.0),
    )
    assert result.passed is False


def test_cost_scorer_handles_missing_cost() -> None:
    result = _score(
        "cost",
        _build_test_case(),
        _build_execution(total_cost_usd=None),
    )
    assert result.passed is True
    assert result.details["reason"] == "cost_unavailable"


def test_confidence_calibration_scorer_checks_min_confidence() -> None:
    passing = _score("confidence_calibration", _build_test_case(), _build_execution(confidence=0.85))
    failing = _score("confidence_calibration", _build_test_case(), _build_execution(confidence=0.4))
    assert passing.passed is True
    assert failing.passed is False


def test_completeness_scorer_flags_missing_keywords() -> None:
    result = _score(
        "completeness",
        _build_test_case(),
        _build_execution(answer="Margins improved after restructuring."),
    )
    assert "missing_keywords" in result.details


def test_relevance_scorer_scores_query_alignment() -> None:
    result = _score("relevance", _build_test_case(), _build_execution())
    assert result.scorer == "relevance"
    assert result.score >= 0.0

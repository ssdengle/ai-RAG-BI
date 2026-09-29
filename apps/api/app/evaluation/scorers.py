from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from apps.api.app.domain.evaluation import (
    EvaluationExecutionContext,
    EvaluationTestCase,
    RunEvaluationConfig,
    ScorerResult,
)
from apps.api.app.domain.retrieval import Citation
from apps.api.app.evaluation.judge import EvaluationJudge


@dataclass(frozen=True)
class ScorerContext:
    test_case: EvaluationTestCase
    execution: EvaluationExecutionContext
    config: RunEvaluationConfig
    context_text: str = ""


class Scorer(Protocol):
    name: str

    async def score(self, context: ScorerContext) -> ScorerResult:
        """Compute a normalized score between 0.0 and 1.0."""


def _threshold_for(scorer_name: str, test_case: EvaluationTestCase, config: RunEvaluationConfig) -> float:
    if scorer_name in test_case.rubric.scorer_thresholds:
        return float(test_case.rubric.scorer_thresholds[scorer_name])
    return config.pass_threshold


def _build_result(scorer: str, score: float, *, threshold: float, details: dict[str, Any] | None = None) -> ScorerResult:
    normalized = round(max(0.0, min(score, 1.0)), 4)
    return ScorerResult(
        scorer=scorer,
        score=normalized,
        passed=normalized >= threshold,
        details=details or {},
    )


def _citation_ids(citations: list[Citation]) -> list[str]:
    return [citation.chunk_id for citation in citations]


def _context_from_execution(execution: EvaluationExecutionContext) -> str:
    snippets = [citation.snippet for citation in execution.citations if citation.snippet]
    return "\n".join(snippets)


class AnswerAccuracyScorer:
    name = "answer_accuracy"

    def __init__(self, judge: EvaluationJudge) -> None:
        self._judge = judge

    async def score(self, context: ScorerContext) -> ScorerResult:
        threshold = _threshold_for(self.name, context.test_case, context.config)
        judge_score = await self._judge.score_similarity(
            actual=context.execution.answer,
            expected=context.test_case.expected_answer.text,
            context=context.context_text,
        )
        return _build_result(self.name, judge_score.score, threshold=threshold, details={"rationale": judge_score.rationale})


class GroundednessScorer:
    name = "groundedness"

    def __init__(self, judge: EvaluationJudge) -> None:
        self._judge = judge

    async def score(self, context: ScorerContext) -> ScorerResult:
        threshold = _threshold_for(self.name, context.test_case, context.config)
        context_text = context.context_text or _context_from_execution(context.execution)
        judge_score = await self._judge.score_groundedness(
            answer=context.execution.answer,
            context=context_text,
        )
        return _build_result(self.name, judge_score.score, threshold=threshold, details={"rationale": judge_score.rationale})


class CitationCorrectnessScorer:
    name = "citation_correctness"

    async def score(self, context: ScorerContext) -> ScorerResult:
        threshold = _threshold_for(self.name, context.test_case, context.config)
        required = set(context.test_case.expected_answer.required_citations)
        actual = set(_citation_ids(context.execution.citations))
        if not required:
            score = 1.0 if actual else 0.5
            return _build_result(self.name, score, threshold=threshold, details={"required": [], "actual": sorted(actual)})

        matched = required & actual
        score = len(matched) / len(required)
        return _build_result(
            self.name,
            score,
            threshold=threshold,
            details={"required": sorted(required), "actual": sorted(actual), "matched": sorted(matched)},
        )


class HallucinationRiskScorer:
    name = "hallucination_risk"

    async def score(self, context: ScorerContext) -> ScorerResult:
        threshold = _threshold_for(self.name, context.test_case, context.config)
        answer = context.execution.answer.lower()
        context_text = (context.context_text or _context_from_execution(context.execution)).lower()
        if not answer.strip():
            return _build_result(self.name, 0.0, threshold=threshold, details={"reason": "empty_answer"})

        answer_tokens = {token for token in answer.split() if len(token) > 4}
        context_tokens = set(context_text.split())
        unsupported = [token for token in answer_tokens if token not in context_tokens]
        risk = len(unsupported) / max(len(answer_tokens), 1)
        score = 1.0 - risk
        return _build_result(
            self.name,
            score,
            threshold=threshold,
            details={"unsupported_tokens": unsupported[:10], "risk": round(risk, 4)},
        )


class CompletenessScorer:
    name = "completeness"

    def __init__(self, judge: EvaluationJudge) -> None:
        self._judge = judge

    async def score(self, context: ScorerContext) -> ScorerResult:
        threshold = _threshold_for(self.name, context.test_case, context.config)
        judge_score = await self._judge.score_completeness(
            answer=context.execution.answer,
            expected=context.test_case.expected_answer.text,
        )
        missing_keywords = [
            keyword
            for keyword in context.test_case.expected_answer.required_keywords
            if keyword.lower() not in context.execution.answer.lower()
        ]
        keyword_penalty = len(missing_keywords) / max(len(context.test_case.expected_answer.required_keywords), 1)
        blended = judge_score.score * (1.0 - (0.5 * keyword_penalty))
        return _build_result(
            self.name,
            blended,
            threshold=threshold,
            details={"rationale": judge_score.rationale, "missing_keywords": missing_keywords},
        )


class RelevanceScorer:
    name = "relevance"

    def __init__(self, judge: EvaluationJudge) -> None:
        self._judge = judge

    async def score(self, context: ScorerContext) -> ScorerResult:
        threshold = _threshold_for(self.name, context.test_case, context.config)
        judge_score = await self._judge.score_relevance(
            answer=context.execution.answer,
            query=context.test_case.query,
        )
        return _build_result(self.name, judge_score.score, threshold=threshold, details={"rationale": judge_score.rationale})


class ConfidenceCalibrationScorer:
    name = "confidence_calibration"

    async def score(self, context: ScorerContext) -> ScorerResult:
        threshold = _threshold_for(self.name, context.test_case, context.config)
        confidence = context.execution.confidence
        if confidence is None:
            return _build_result(self.name, 0.0, threshold=threshold, details={"reason": "confidence_unavailable"})

        min_confidence = context.test_case.expected_answer.min_confidence
        if min_confidence is not None:
            passed = confidence >= min_confidence
            return ScorerResult(
                scorer=self.name,
                score=round(confidence, 4),
                passed=passed,
                details={"confidence": confidence, "min_confidence": min_confidence},
            )

        return _build_result(self.name, confidence, threshold=threshold, details={"confidence": confidence})


class LatencyScorer:
    name = "latency"

    async def score(self, context: ScorerContext) -> ScorerResult:
        threshold = _threshold_for(self.name, context.test_case, context.config)
        latency_ms = context.execution.latency_ms
        limit = context.config.latency_threshold_ms
        if latency_ms <= limit:
            score = 1.0
        else:
            overrun_ratio = (latency_ms - limit) / max(limit, 1.0)
            score = max(0.0, 1.0 - overrun_ratio)
        return _build_result(
            self.name,
            score,
            threshold=threshold,
            details={"latency_ms": latency_ms, "threshold_ms": limit},
        )


class CostScorer:
    name = "cost"

    async def score(self, context: ScorerContext) -> ScorerResult:
        threshold = _threshold_for(self.name, context.test_case, context.config)
        cost = context.execution.total_cost_usd
        if cost is None:
            return _build_result(self.name, 1.0, threshold=threshold, details={"reason": "cost_unavailable"})

        limit = context.config.cost_threshold_usd
        if limit is None:
            return _build_result(self.name, 1.0, threshold=threshold, details={"cost_usd": cost})

        if cost <= limit:
            score = 1.0
        else:
            overrun_ratio = (cost - limit) / max(limit, 1e-9)
            score = max(0.0, 1.0 - overrun_ratio)
        return _build_result(self.name, score, threshold=threshold, details={"cost_usd": cost, "threshold_usd": limit})


@dataclass
class ScorerRegistry:
    scorers: dict[str, Scorer] = field(default_factory=dict)

    def get(self, name: str) -> Scorer | None:
        return self.scorers.get(name)

    def resolve(self, names: list[str]) -> list[Scorer]:
        resolved: list[Scorer] = []
        for name in names:
            scorer = self.get(name)
            if scorer is not None:
                resolved.append(scorer)
        return resolved


def build_default_scorer_registry(judge: EvaluationJudge) -> ScorerRegistry:
    return ScorerRegistry(
        scorers={
            "answer_accuracy": AnswerAccuracyScorer(judge),
            "groundedness": GroundednessScorer(judge),
            "citation_correctness": CitationCorrectnessScorer(),
            "hallucination_risk": HallucinationRiskScorer(),
            "completeness": CompletenessScorer(judge),
            "relevance": RelevanceScorer(judge),
            "confidence_calibration": ConfidenceCalibrationScorer(),
            "latency": LatencyScorer(),
            "cost": CostScorer(),
        }
    )

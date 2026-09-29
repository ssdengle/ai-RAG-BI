from __future__ import annotations

import asyncio

from apps.api.app.evaluation.judge import HeuristicEvaluationJudge


def test_heuristic_judge_scores_similar_answers_high() -> None:
    judge = HeuristicEvaluationJudge()

    score = asyncio.run(
        judge.score_similarity(
            actual="Revenue increased steadily across all regions.",
            expected="Revenue increased steadily.",
        )
    )

    assert score.score >= 0.5


def test_heuristic_judge_scores_empty_answer_zero() -> None:
    judge = HeuristicEvaluationJudge()

    score = asyncio.run(judge.score_similarity(actual="", expected="Revenue increased."))

    assert score.score == 0.0


def test_heuristic_judge_groundedness_requires_context_overlap() -> None:
    judge = HeuristicEvaluationJudge()

    grounded = asyncio.run(
        judge.score_groundedness(
            answer="Revenue increased steadily.",
            context="Revenue increased steadily in Q1.",
        )
    )
    ungrounded = asyncio.run(
        judge.score_groundedness(
            answer="Margins collapsed unexpectedly.",
            context="Revenue increased steadily in Q1.",
        )
    )

    assert grounded.score > ungrounded.score

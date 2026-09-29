from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from apps.api.app.rag.llm import ChatCompletionProvider, ChatMessage


@dataclass(frozen=True)
class JudgeScore:
    score: float
    rationale: str


class EvaluationJudge(Protocol):
    async def score_similarity(self, *, actual: str, expected: str, context: str = "") -> JudgeScore:
        """Score semantic similarity between actual and expected answers."""

    async def score_groundedness(self, *, answer: str, context: str) -> JudgeScore:
        """Score whether the answer is grounded in the provided context."""

    async def score_completeness(self, *, answer: str, expected: str) -> JudgeScore:
        """Score whether the answer covers expected content."""

    async def score_relevance(self, *, answer: str, query: str) -> JudgeScore:
        """Score whether the answer is relevant to the query."""


class HeuristicEvaluationJudge:
    """Deterministic judge for unit tests and offline evaluation without LLM calls."""

    async def score_similarity(self, *, actual: str, expected: str, context: str = "") -> JudgeScore:
        actual_norm = _normalize(actual)
        expected_norm = _normalize(expected)
        if not actual_norm:
            return JudgeScore(score=0.0, rationale="Empty actual answer.")
        if not expected_norm:
            return JudgeScore(score=1.0 if actual_norm else 0.0, rationale="No expected answer provided.")

        expected_tokens = set(expected_norm.split())
        actual_tokens = set(actual_norm.split())
        overlap = len(expected_tokens & actual_tokens)
        score = overlap / max(len(expected_tokens), 1)
        return JudgeScore(score=round(min(score, 1.0), 4), rationale="Token overlap heuristic.")

    async def score_groundedness(self, *, answer: str, context: str) -> JudgeScore:
        answer_norm = _normalize(answer)
        context_norm = _normalize(context)
        if not answer_norm:
            return JudgeScore(score=0.0, rationale="Empty answer.")
        if not context_norm:
            return JudgeScore(score=0.0, rationale="No context available.")

        answer_tokens = set(answer_norm.split())
        context_tokens = set(context_norm.split())
        overlap = len(answer_tokens & context_tokens)
        score = overlap / max(len(answer_tokens), 1)
        return JudgeScore(score=round(min(score, 1.0), 4), rationale="Answer/context token overlap.")

    async def score_completeness(self, *, answer: str, expected: str) -> JudgeScore:
        return await self.score_similarity(actual=answer, expected=expected)

    async def score_relevance(self, *, answer: str, query: str) -> JudgeScore:
        return await self.score_similarity(actual=answer, expected=query)


class LLMEvaluationJudge:
    """Provider-backed judge that delegates qualitative scoring to an LLM."""

    def __init__(self, *, chat_provider: ChatCompletionProvider) -> None:
        self._chat_provider = chat_provider

    async def score_similarity(self, *, actual: str, expected: str, context: str = "") -> JudgeScore:
        prompt = (
            "Rate answer accuracy from 0.0 to 1.0.\n"
            f"Expected answer: {expected}\n"
            f"Actual answer: {actual}\n"
            "Respond with only a decimal score."
        )
        return await self._score_from_prompt(prompt, default_rationale="LLM answer accuracy score.")

    async def score_groundedness(self, *, answer: str, context: str) -> JudgeScore:
        prompt = (
            "Rate groundedness from 0.0 to 1.0 based on whether the answer is supported by context.\n"
            f"Context: {context}\n"
            f"Answer: {answer}\n"
            "Respond with only a decimal score."
        )
        return await self._score_from_prompt(prompt, default_rationale="LLM groundedness score.")

    async def score_completeness(self, *, answer: str, expected: str) -> JudgeScore:
        prompt = (
            "Rate completeness from 0.0 to 1.0 based on whether the answer covers the expected content.\n"
            f"Expected content: {expected}\n"
            f"Answer: {answer}\n"
            "Respond with only a decimal score."
        )
        return await self._score_from_prompt(prompt, default_rationale="LLM completeness score.")

    async def score_relevance(self, *, answer: str, query: str) -> JudgeScore:
        prompt = (
            "Rate relevance from 0.0 to 1.0 based on whether the answer addresses the query.\n"
            f"Query: {query}\n"
            f"Answer: {answer}\n"
            "Respond with only a decimal score."
        )
        return await self._score_from_prompt(prompt, default_rationale="LLM relevance score.")

    async def _score_from_prompt(self, prompt: str, *, default_rationale: str) -> JudgeScore:
        result = await self._chat_provider.complete(
            [
                ChatMessage(role="system", content="You are an evaluation judge. Return only a numeric score."),
                ChatMessage(role="user", content=prompt),
            ]
        )
        score = _parse_score(result.text)
        return JudgeScore(score=score, rationale=default_rationale)


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _parse_score(text: str) -> float:
    cleaned = text.strip().replace("%", "")
    try:
        value = float(cleaned)
    except ValueError:
        return 0.0
    return round(max(0.0, min(value, 1.0)), 4)

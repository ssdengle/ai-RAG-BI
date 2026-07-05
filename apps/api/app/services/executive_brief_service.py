from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.core.errors import DomainError
from apps.api.app.core.logging import get_logger
from apps.api.app.domain.bi import ExecutiveBrief
from apps.api.app.domain.retrieval import RetrievalFilters, RetrievalMode
from apps.api.app.repositories.bi_repository import BiRepository
from apps.api.app.services.question_answering_service import QuestionAnsweringService

HUMAN_REVIEW_CONFIDENCE_THRESHOLD = 0.75


class ExecutiveBriefService:
    def __init__(
        self,
        *,
        bi_repository: BiRepository,
        question_answering_service: QuestionAnsweringService,
        prompt_path: Path | None = None,
    ) -> None:
        self._bi_repository = bi_repository
        self._question_answering_service = question_answering_service
        self._prompt_path = prompt_path
        self._logger = get_logger("api.executive_brief_service")

    async def generate_executive_brief(
        self,
        session: AsyncSession,
        *,
        topic: str,
        company_id: str | None = None,
        mode: RetrievalMode = "hybrid",
        top_k: int = 6,
    ) -> ExecutiveBrief:
        company_name = None
        filters = RetrievalFilters()
        if company_id is not None:
            profile = await self._bi_repository.get_company_profile(session, company_id)
            if profile is None:
                raise DomainError(
                    "Company profile was not found.",
                    details=company_id,
                    code="company_profile_not_found",
                    status_code=404,
                )
            company_name = profile.display_name
            filters = RetrievalFilters(company=profile.name)

        question = _build_brief_question(topic=topic, company_name=company_name)
        qa_result = await self._question_answering_service.answer(
            session,
            question=question,
            mode=mode,
            filters=filters,
            top_k=top_k,
        )

        human_review_recommended = _requires_human_review(
            confidence=qa_result.confidence,
            citation_count=len(qa_result.citations),
            answer=qa_result.answer,
        )
        key_points = _extract_key_points(qa_result.answer)

        brief = ExecutiveBrief(
            title=_build_brief_title(topic=topic, company_name=company_name),
            summary=qa_result.answer,
            key_points=key_points,
            citations=qa_result.citations,
            confidence=qa_result.confidence,
            human_review_recommended=human_review_recommended,
            llm_provider=qa_result.llm_provider,
            llm_model=qa_result.llm_model,
            company_id=company_id,
            company_name=company_name,
            topic=topic,
        )
        self._logger.info(
            "executive_brief.generated",
            company_id=company_id,
            topic=topic,
            confidence=brief.confidence,
            human_review_recommended=brief.human_review_recommended,
        )
        return brief


def _build_brief_question(*, topic: str, company_name: str | None) -> str:
    if company_name:
        return (
            f"Prepare an executive business intelligence brief about {topic} for {company_name}. "
            "Summarize the most important grounded findings, risks, and opportunities."
        )
    return (
        f"Prepare an executive business intelligence brief about {topic}. "
        "Summarize the most important grounded findings, risks, and opportunities."
    )


def _build_brief_title(*, topic: str, company_name: str | None) -> str:
    if company_name:
        return f"{company_name}: {topic}"
    return topic


def _requires_human_review(*, confidence: float, citation_count: int, answer: str) -> bool:
    if not answer.strip() or answer.startswith("Not enough information"):
        return True
    if citation_count == 0:
        return True
    return confidence < HUMAN_REVIEW_CONFIDENCE_THRESHOLD


def _extract_key_points(answer: str) -> list[str]:
    lines = [line.strip(" -\t") for line in answer.splitlines() if line.strip()]
    if len(lines) >= 2:
        return lines[:5]
    sentences = [part.strip() for part in answer.split(".") if part.strip()]
    return sentences[:5]

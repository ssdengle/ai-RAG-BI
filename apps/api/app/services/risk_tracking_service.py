from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.core.errors import DomainError
from apps.api.app.core.logging import get_logger
from apps.api.app.domain.bi import RiskCategorySummary, RiskComparisonResult, RiskEvidence, RiskSummary
from apps.api.app.domain.retrieval import Citation, RetrievalFilters, RetrievalMode
from apps.api.app.repositories.bi_repository import BiRepository
from apps.api.app.services.evidence_classifier import (
    build_risk_summary_text,
    classify_risk_categories,
    summarize_chunk_text,
)
from apps.api.app.services.retrieval_service import RetrievalService


RISK_RETRIEVAL_QUERY = "What are the key business risks, regulatory issues, and operational challenges?"


class RiskTrackingService:
    def __init__(
        self,
        *,
        bi_repository: BiRepository,
        retrieval_service: RetrievalService,
    ) -> None:
        self._bi_repository = bi_repository
        self._retrieval_service = retrieval_service
        self._logger = get_logger("api.risk_tracking_service")

    async def extract_and_store_risks(
        self,
        session: AsyncSession,
        *,
        company_id: str,
        mode: RetrievalMode = "hybrid",
        top_k: int = 8,
    ) -> list[RiskEvidence]:
        profile = await self._require_company(session, company_id)
        retrieval = await self._retrieval_service.retrieve(
            session,
            query=RISK_RETRIEVAL_QUERY,
            mode=mode,
            filters=RetrievalFilters(company=profile.name),
            top_k=top_k,
        )
        extracted = _build_risk_evidence(profile.company_id, retrieval.chunks)
        stored = await self._bi_repository.replace_risk_evidence(
            session,
            company_id=company_id,
            evidence_items=extracted,
        )
        await session.commit()
        self._logger.info(
            "risk_tracking.extracted",
            company_id=company_id,
            evidence_count=len(stored),
        )
        return stored

    async def summarize_risks(
        self,
        session: AsyncSession,
        *,
        company_id: str,
        refresh: bool = False,
        mode: RetrievalMode = "hybrid",
        top_k: int = 8,
    ) -> RiskSummary:
        profile = await self._require_company(session, company_id)
        if refresh:
            await self.extract_and_store_risks(
                session,
                company_id=company_id,
                mode=mode,
                top_k=top_k,
            )
        evidence = await self._bi_repository.list_risk_evidence(session, company_id=company_id)
        return _build_risk_summary(profile.company_id, profile.display_name, evidence)

    async def compare_risks(
        self,
        session: AsyncSession,
        *,
        company_ids: list[str],
        refresh: bool = False,
        mode: RetrievalMode = "hybrid",
        top_k: int = 8,
    ) -> RiskComparisonResult:
        summaries = []
        for company_id in company_ids:
            summaries.append(
                await self.summarize_risks(
                    session,
                    company_id=company_id,
                    refresh=refresh,
                    mode=mode,
                    top_k=top_k,
                )
            )

        category_sets = {
            summary.company_id: {category.category for category in summary.categories}
            for summary in summaries
        }
        all_categories = set().union(*category_sets.values()) if category_sets else set()
        shared_categories = sorted(
            category
            for category in all_categories
            if all(category in categories for categories in category_sets.values())
        )
        unique_categories_by_company = {
            summary.company_id: sorted(category_sets[summary.company_id] - set(shared_categories))
            for summary in summaries
        }
        return RiskComparisonResult(
            companies=summaries,
            shared_categories=shared_categories,
            unique_categories_by_company=unique_categories_by_company,
        )

    async def _require_company(self, session: AsyncSession, company_id: str):
        profile = await self._bi_repository.get_company_profile(session, company_id)
        if profile is None:
            raise DomainError(
                "Company profile was not found.",
                details=company_id,
                code="company_profile_not_found",
                status_code=404,
            )
        return profile


def _build_risk_evidence(company_id: str, chunks) -> list[RiskEvidence]:
    extracted_at = datetime.now(timezone.utc)
    evidence_items: list[RiskEvidence] = []

    for chunk in chunks:
        categories = classify_risk_categories(chunk.text)
        for category in categories:
            evidence_items.append(
                RiskEvidence(
                    evidence_id=str(uuid4()),
                    company_id=company_id,
                    document_id=chunk.document_id,
                    chunk_id=chunk.chunk_id,
                    risk_category=category,
                    summary_text=build_risk_summary_text(category, chunk),
                    snippet=summarize_chunk_text(chunk.text),
                    score=chunk.score,
                    extracted_at=extracted_at,
                )
            )
    return evidence_items


def _build_risk_summary(company_id: str, company_name: str, evidence: list[RiskEvidence]) -> RiskSummary:
    if not evidence:
        return RiskSummary(
            company_id=company_id,
            company_name=company_name,
            total_evidence_count=0,
            categories=[],
            citations=[],
            evidence_available=False,
        )

    grouped: dict[str, list[RiskEvidence]] = {}
    for item in evidence:
        grouped.setdefault(item.risk_category, []).append(item)

    categories = []
    citations: list[Citation] = []
    for category, items in sorted(grouped.items()):
        top_items = sorted(items, key=lambda item: item.score, reverse=True)[:3]
        categories.append(
            RiskCategorySummary(
                category=category,
                count=len(items),
                top_snippets=[item.snippet for item in top_items],
                average_score=round(sum(item.score for item in items) / len(items), 4),
            )
        )
        for item in top_items:
            citations.append(
                Citation(
                    document_id=item.document_id,
                    title=None,
                    chunk_id=item.chunk_id,
                    page_number=None,
                    score=item.score,
                    snippet=item.snippet,
                )
            )

    return RiskSummary(
        company_id=company_id,
        company_name=company_name,
        total_evidence_count=len(evidence),
        categories=categories,
        citations=_dedupe_citations(citations),
        evidence_available=True,
    )


def _dedupe_citations(citations: list[Citation]) -> list[Citation]:
    seen: set[tuple[str, str]] = set()
    unique: list[Citation] = []
    for citation in citations:
        key = (citation.document_id, citation.chunk_id)
        if key in seen:
            continue
        seen.add(key)
        unique.append(citation)
    return unique

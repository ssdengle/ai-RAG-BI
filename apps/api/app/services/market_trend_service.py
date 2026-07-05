from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.core.errors import DomainError
from apps.api.app.core.logging import get_logger
from apps.api.app.domain.bi import TrendEvidence, TrendSummary, TrendTopicSummary
from apps.api.app.domain.retrieval import Citation, RetrievalFilters, RetrievalMode
from apps.api.app.repositories.bi_repository import BiRepository
from apps.api.app.services.evidence_classifier import (
    build_trend_summary_text,
    classify_trend_topics,
    summarize_chunk_text,
)
from apps.api.app.services.retrieval_service import RetrievalService


TREND_RETRIEVAL_QUERY = (
    "What market trends, revenue growth, expansion initiatives, and strategic developments are described?"
)


class MarketTrendService:
    def __init__(
        self,
        *,
        bi_repository: BiRepository,
        retrieval_service: RetrievalService,
    ) -> None:
        self._bi_repository = bi_repository
        self._retrieval_service = retrieval_service
        self._logger = get_logger("api.market_trend_service")

    async def extract_and_store_trends(
        self,
        session: AsyncSession,
        *,
        company_id: str,
        document_type: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        mode: RetrievalMode = "hybrid",
        top_k: int = 8,
    ) -> list[TrendEvidence]:
        profile = await self._require_company(session, company_id)
        retrieval = await self._retrieval_service.retrieve(
            session,
            query=TREND_RETRIEVAL_QUERY,
            mode=mode,
            filters=RetrievalFilters(
                company=profile.name,
                document_type=document_type,
                date_from=date_from,
                date_to=date_to,
            ),
            top_k=top_k,
        )
        extracted = _build_trend_evidence(profile.company_id, retrieval.chunks)
        stored = await self._bi_repository.replace_trend_evidence(
            session,
            company_id=company_id,
            evidence_items=extracted,
        )
        await session.commit()
        self._logger.info(
            "market_trend.extracted",
            company_id=company_id,
            evidence_count=len(stored),
        )
        return stored

    async def summarize_trends(
        self,
        session: AsyncSession,
        *,
        company_id: str | None = None,
        document_type: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        refresh: bool = False,
        mode: RetrievalMode = "hybrid",
        top_k: int = 8,
    ) -> TrendSummary:
        company_name = None
        if company_id is not None:
            profile = await self._require_company(session, company_id)
            company_name = profile.display_name
            if refresh:
                await self.extract_and_store_trends(
                    session,
                    company_id=company_id,
                    document_type=document_type,
                    date_from=date_from,
                    date_to=date_to,
                    mode=mode,
                    top_k=top_k,
                )

        evidence = await self._bi_repository.list_trend_evidence(
            session,
            company_id=company_id,
            document_type=document_type,
            date_from=date_from,
            date_to=date_to,
        )
        return _build_trend_summary(
            company_id=company_id,
            company_name=company_name,
            document_type=document_type,
            date_from=date_from,
            date_to=date_to,
            evidence=evidence,
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


def _build_trend_evidence(company_id: str, chunks) -> list[TrendEvidence]:
    extracted_at = datetime.now(timezone.utc)
    evidence_items: list[TrendEvidence] = []

    for chunk in chunks:
        topics = classify_trend_topics(chunk.text)
        if not topics:
            continue
        document_type = chunk.document_metadata.get("document_type")
        document_date = chunk.document_metadata.get("date")
        for topic in topics:
            evidence_items.append(
                TrendEvidence(
                    evidence_id=str(uuid4()),
                    company_id=company_id,
                    document_id=chunk.document_id,
                    chunk_id=chunk.chunk_id,
                    trend_topic=topic,
                    document_type=document_type if isinstance(document_type, str) else None,
                    document_date=document_date if isinstance(document_date, str) else None,
                    summary_text=build_trend_summary_text(topic, chunk),
                    snippet=summarize_chunk_text(chunk.text),
                    score=chunk.score,
                    extracted_at=extracted_at,
                )
            )
    return evidence_items


def _build_trend_summary(
    *,
    company_id: str | None,
    company_name: str | None,
    document_type: str | None,
    date_from: str | None,
    date_to: str | None,
    evidence: list[TrendEvidence],
) -> TrendSummary:
    if not evidence:
        return TrendSummary(
            company_id=company_id,
            company_name=company_name,
            document_type=document_type,
            date_from=date_from,
            date_to=date_to,
            total_evidence_count=0,
            topics=[],
            citations=[],
            evidence_available=False,
        )

    grouped: dict[str, list[TrendEvidence]] = {}
    for item in evidence:
        grouped.setdefault(item.trend_topic, []).append(item)

    topics = []
    citations: list[Citation] = []
    for topic, items in sorted(grouped.items()):
        top_items = sorted(items, key=lambda item: item.score, reverse=True)[:3]
        document_types: dict[str, int] = {}
        for item in items:
            doc_type = item.document_type or "unknown"
            document_types[doc_type] = document_types.get(doc_type, 0) + 1
        topics.append(
            TrendTopicSummary(
                topic=topic,
                count=len(items),
                document_types=document_types,
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

    return TrendSummary(
        company_id=company_id,
        company_name=company_name,
        document_type=document_type,
        date_from=date_from,
        date_to=date_to,
        total_evidence_count=len(evidence),
        topics=topics,
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

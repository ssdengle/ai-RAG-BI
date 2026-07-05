from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.core.errors import DomainError
from apps.api.app.core.logging import get_logger
from apps.api.app.domain.bi import CompanyComparisonMetric, CompanyComparisonResult, CompetitorRelationship
from apps.api.app.domain.documents import IndexingStatus
from apps.api.app.domain.retrieval import RetrievalFilters, RetrievalMode
from apps.api.app.repositories.bi_repository import BiRepository
from apps.api.app.services.retrieval_service import RetrievalService


class CompetitorService:
    def __init__(
        self,
        *,
        bi_repository: BiRepository,
        retrieval_service: RetrievalService,
    ) -> None:
        self._bi_repository = bi_repository
        self._retrieval_service = retrieval_service
        self._logger = get_logger("api.competitor_service")

    async def add_competitor(
        self,
        session: AsyncSession,
        *,
        company_id: str,
        competitor_company_id: str,
        relationship_type: str | None = None,
        notes: str | None = None,
    ) -> CompetitorRelationship:
        if company_id == competitor_company_id:
            raise DomainError(
                "A company cannot be listed as its own competitor.",
                details=company_id,
                code="invalid_competitor_relationship",
                status_code=400,
            )

        company = await self._bi_repository.get_company_profile(session, company_id)
        competitor = await self._bi_repository.get_company_profile(session, competitor_company_id)
        if company is None or competitor is None:
            raise DomainError(
                "Company profile was not found.",
                details={"company_id": company_id, "competitor_company_id": competitor_company_id},
                code="company_profile_not_found",
                status_code=404,
            )

        relationship = await self._bi_repository.add_competitor_relationship(
            session,
            company_id=company_id,
            competitor_company_id=competitor_company_id,
            relationship_type=relationship_type,
            notes=notes,
        )
        await session.commit()
        return relationship

    async def list_competitors(
        self,
        session: AsyncSession,
        *,
        company_id: str,
    ) -> list[CompetitorRelationship]:
        company = await self._bi_repository.get_company_profile(session, company_id)
        if company is None:
            raise DomainError(
                "Company profile was not found.",
                details=company_id,
                code="company_profile_not_found",
                status_code=404,
            )
        return await self._bi_repository.list_competitor_relationships(session, company_id=company_id)

    async def compare_companies(
        self,
        session: AsyncSession,
        *,
        company_ids: list[str],
        query: str,
        mode: RetrievalMode = "hybrid",
        top_k: int = 5,
    ) -> CompanyComparisonResult:
        if len(company_ids) < 2:
            raise DomainError(
                "At least two companies are required for comparison.",
                details=company_ids,
                code="invalid_company_comparison",
                status_code=400,
            )

        metrics: list[CompanyComparisonMetric] = []
        all_citations = []

        for company_id in company_ids:
            metrics_result = await self._bi_repository.get_company_metrics(session, company_id=company_id)
            if metrics_result is None:
                raise DomainError(
                    "Company profile was not found.",
                    details=company_id,
                    code="company_profile_not_found",
                    status_code=404,
                )

            profile, documents, documents_by_type = metrics_result
            retrieval = await self._retrieval_service.retrieve(
                session,
                query=query,
                mode=mode,
                filters=RetrievalFilters(company=profile.name),
                top_k=top_k,
            )
            all_citations.extend(retrieval.citations)
            indexed_document_count = sum(
                1 for document in documents if document.indexing_status == IndexingStatus.INDEXED
            )
            metrics.append(
                CompanyComparisonMetric(
                    company_id=profile.company_id,
                    company_name=profile.display_name,
                    document_count=len(documents),
                    total_chunks=sum(document.chunk_count for document in documents),
                    indexed_document_count=indexed_document_count,
                    top_document_types=documents_by_type,
                    evidence_snippets=[chunk.text for chunk in retrieval.chunks[:3]],
                )
            )

        shared_topics = _find_shared_snippet_terms(
            [snippet for metric in metrics for snippet in metric.evidence_snippets]
        )
        return CompanyComparisonResult(
            companies=metrics,
            comparison_query=query,
            shared_topics=shared_topics,
            citations=_dedupe_citations(all_citations),
        )


def _find_shared_snippet_terms(snippets: list[str]) -> list[str]:
    tokens = []
    for snippet in snippets:
        tokens.extend(word.lower() for word in snippet.split() if len(word) > 4)
    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    return sorted(token for token, count in counts.items() if count >= 2)[:5]


def _dedupe_citations(citations):
    seen: set[tuple[str, str]] = set()
    unique = []
    for citation in citations:
        key = (citation.document_id, citation.chunk_id)
        if key in seen:
            continue
        seen.add(key)
        unique.append(citation)
    return unique

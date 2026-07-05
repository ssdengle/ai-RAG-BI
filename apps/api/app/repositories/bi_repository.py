from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence
from uuid import uuid4

from sqlalchemy import Date, cast, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.api.app.domain.bi import (
    CompanyDocumentSummary,
    CompanyProfile,
    CompanyProfileDetail,
    CompetitorRelationship,
    RiskEvidence,
    TrendEvidence,
)
from apps.api.app.domain.documents import IndexingStatus
from apps.api.app.repositories.models import (
    CompanyProfileModel,
    CompetitorRelationshipModel,
    DocumentModel,
    RiskEvidenceModel,
    TrendEvidenceModel,
)


class BiRepository:
    async def create_company_profile(
        self,
        session: AsyncSession,
        *,
        name: str,
        display_name: str,
        industry: str | None = None,
        description: str | None = None,
        metadata: dict | None = None,
    ) -> CompanyProfile:
        profile = CompanyProfileModel(
            company_id=str(uuid4()),
            name=name,
            display_name=display_name,
            industry=industry,
            description=description,
            profile_metadata=metadata or {},
        )
        session.add(profile)
        await session.flush()
        await session.refresh(profile)
        return self._to_company_profile(profile)

    async def list_company_profiles(self, session: AsyncSession) -> list[CompanyProfile]:
        result = await session.execute(
            select(CompanyProfileModel).order_by(CompanyProfileModel.display_name.asc())
        )
        return [self._to_company_profile(profile) for profile in result.scalars().all()]

    async def get_company_profile(
        self,
        session: AsyncSession,
        company_id: str,
    ) -> CompanyProfile | None:
        profile = await session.get(CompanyProfileModel, company_id)
        if profile is None:
            return None
        return self._to_company_profile(profile)

    async def get_company_profile_by_name(
        self,
        session: AsyncSession,
        name: str,
    ) -> CompanyProfile | None:
        result = await session.execute(
            select(CompanyProfileModel).where(CompanyProfileModel.name == name)
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            return None
        return self._to_company_profile(profile)

    async def get_company_profile_detail(
        self,
        session: AsyncSession,
        company_id: str,
    ) -> CompanyProfileDetail | None:
        profile = await self.get_company_profile(session, company_id)
        if profile is None:
            return None

        documents = await self.list_documents_for_company(session, company_name=profile.name)
        documents_by_type: dict[str, int] = {}
        total_chunks = 0
        indexed_document_count = 0
        summaries: list[CompanyDocumentSummary] = []

        for document in documents:
            document_type = _get_attribute(document.attributes, "document_type") or "unknown"
            documents_by_type[document_type] = documents_by_type.get(document_type, 0) + 1
            total_chunks += document.chunk_count
            if document.indexing_status == IndexingStatus.INDEXED:
                indexed_document_count += 1
            summaries.append(
                CompanyDocumentSummary(
                    document_id=document.document_id,
                    title=document.title,
                    document_type=_get_attribute(document.attributes, "document_type"),
                    source=_get_attribute(document.attributes, "source"),
                    document_date=_get_attribute(document.attributes, "date"),
                    indexing_status=document.indexing_status.value,
                    chunk_count=document.chunk_count,
                )
            )

        return CompanyProfileDetail(
            profile=profile,
            document_count=len(documents),
            documents_by_type=documents_by_type,
            total_chunks=total_chunks,
            indexed_document_count=indexed_document_count,
            documents=summaries,
        )

    async def list_documents_for_company(
        self,
        session: AsyncSession,
        *,
        company_name: str,
    ) -> list:
        from apps.api.app.repositories.document_repository import DocumentRepository

        stmt = select(DocumentModel).where(
            DocumentModel.attributes["company"].astext == company_name
        ).order_by(DocumentModel.created_at.desc())
        result = await session.execute(stmt)
        documents = result.scalars().all()
        return [DocumentRepository._to_persisted_document(document) for document in documents]

    async def add_competitor_relationship(
        self,
        session: AsyncSession,
        *,
        company_id: str,
        competitor_company_id: str,
        relationship_type: str | None = None,
        notes: str | None = None,
    ) -> CompetitorRelationship:
        relationship = CompetitorRelationshipModel(
            relationship_id=str(uuid4()),
            company_id=company_id,
            competitor_company_id=competitor_company_id,
            relationship_type=relationship_type,
            notes=notes,
        )
        session.add(relationship)
        await session.flush()
        competitor = await self.get_company_profile(session, competitor_company_id)
        competitor_name = competitor.display_name if competitor else competitor_company_id
        return self._to_competitor_relationship(relationship, competitor_name=competitor_name)

    async def list_competitor_relationships(
        self,
        session: AsyncSession,
        *,
        company_id: str,
    ) -> list[CompetitorRelationship]:
        result = await session.execute(
            select(CompetitorRelationshipModel, CompanyProfileModel)
            .join(
                CompanyProfileModel,
                CompetitorRelationshipModel.competitor_company_id == CompanyProfileModel.company_id,
            )
            .where(CompetitorRelationshipModel.company_id == company_id)
            .order_by(CompanyProfileModel.display_name.asc())
        )
        return [
            self._to_competitor_relationship(relationship, competitor_name=competitor.display_name)
            for relationship, competitor in result.all()
        ]

    async def replace_risk_evidence(
        self,
        session: AsyncSession,
        *,
        company_id: str,
        evidence_items: Sequence[RiskEvidence],
    ) -> list[RiskEvidence]:
        await session.execute(
            delete(RiskEvidenceModel).where(RiskEvidenceModel.company_id == company_id)
        )
        models = [
            RiskEvidenceModel(
                evidence_id=item.evidence_id,
                company_id=item.company_id,
                document_id=item.document_id,
                chunk_id=item.chunk_id,
                risk_category=item.risk_category,
                summary_text=item.summary_text,
                snippet=item.snippet,
                score=item.score,
                extracted_at=item.extracted_at,
            )
            for item in evidence_items
        ]
        session.add_all(models)
        await session.flush()
        return list(evidence_items)

    async def list_risk_evidence(
        self,
        session: AsyncSession,
        *,
        company_id: str,
    ) -> list[RiskEvidence]:
        result = await session.execute(
            select(RiskEvidenceModel)
            .where(RiskEvidenceModel.company_id == company_id)
            .order_by(RiskEvidenceModel.score.desc())
        )
        return [self._to_risk_evidence(item) for item in result.scalars().all()]

    async def replace_trend_evidence(
        self,
        session: AsyncSession,
        *,
        company_id: str,
        evidence_items: Sequence[TrendEvidence],
    ) -> list[TrendEvidence]:
        await session.execute(
            delete(TrendEvidenceModel).where(TrendEvidenceModel.company_id == company_id)
        )
        models = [
            TrendEvidenceModel(
                evidence_id=item.evidence_id,
                company_id=item.company_id,
                document_id=item.document_id,
                chunk_id=item.chunk_id,
                trend_topic=item.trend_topic,
                document_type=item.document_type,
                document_date=item.document_date,
                summary_text=item.summary_text,
                snippet=item.snippet,
                score=item.score,
                extracted_at=item.extracted_at,
            )
            for item in evidence_items
        ]
        session.add_all(models)
        await session.flush()
        return list(evidence_items)

    async def list_trend_evidence(
        self,
        session: AsyncSession,
        *,
        company_id: str | None = None,
        document_type: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[TrendEvidence]:
        stmt = select(TrendEvidenceModel)
        if company_id:
            stmt = stmt.where(TrendEvidenceModel.company_id == company_id)
        if document_type:
            stmt = stmt.where(TrendEvidenceModel.document_type == document_type)
        if date_from:
            stmt = stmt.where(
                cast(TrendEvidenceModel.document_date, Date) >= cast(date_from, Date)
            )
        if date_to:
            stmt = stmt.where(cast(TrendEvidenceModel.document_date, Date) <= cast(date_to, Date))
        result = await session.execute(stmt.order_by(TrendEvidenceModel.score.desc()))
        return [self._to_trend_evidence(item) for item in result.scalars().all()]

    async def get_company_metrics(
        self,
        session: AsyncSession,
        *,
        company_id: str,
    ) -> tuple[CompanyProfile, list, dict[str, int]] | None:
        profile = await self.get_company_profile(session, company_id)
        if profile is None:
            return None
        documents = await self.list_documents_for_company(session, company_name=profile.name)
        documents_by_type: dict[str, int] = {}
        for document in documents:
            document_type = _get_attribute(document.attributes, "document_type") or "unknown"
            documents_by_type[document_type] = documents_by_type.get(document_type, 0) + 1
        return profile, documents, documents_by_type

    @staticmethod
    def _to_company_profile(profile: CompanyProfileModel) -> CompanyProfile:
        return CompanyProfile(
            company_id=profile.company_id,
            name=profile.name,
            display_name=profile.display_name,
            industry=profile.industry,
            description=profile.description,
            metadata=profile.profile_metadata or {},
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )

    @staticmethod
    def _to_competitor_relationship(
        relationship: CompetitorRelationshipModel,
        *,
        competitor_name: str,
    ) -> CompetitorRelationship:
        return CompetitorRelationship(
            relationship_id=relationship.relationship_id,
            company_id=relationship.company_id,
            competitor_company_id=relationship.competitor_company_id,
            competitor_name=competitor_name,
            relationship_type=relationship.relationship_type,
            notes=relationship.notes,
            created_at=relationship.created_at,
        )

    @staticmethod
    def _to_risk_evidence(item: RiskEvidenceModel) -> RiskEvidence:
        return RiskEvidence(
            evidence_id=item.evidence_id,
            company_id=item.company_id,
            document_id=item.document_id,
            chunk_id=item.chunk_id,
            risk_category=item.risk_category,
            summary_text=item.summary_text,
            snippet=item.snippet,
            score=item.score,
            extracted_at=item.extracted_at,
        )

    @staticmethod
    def _to_trend_evidence(item: TrendEvidenceModel) -> TrendEvidence:
        return TrendEvidence(
            evidence_id=item.evidence_id,
            company_id=item.company_id,
            document_id=item.document_id,
            chunk_id=item.chunk_id,
            trend_topic=item.trend_topic,
            document_type=item.document_type,
            document_date=item.document_date,
            summary_text=item.summary_text,
            snippet=item.snippet,
            score=item.score,
            extracted_at=item.extracted_at,
        )


def _get_attribute(attributes: dict, key: str) -> str | None:
    value = attributes.get(key)
    return value if isinstance(value, str) else None

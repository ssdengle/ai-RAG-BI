from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.core.config import get_request_settings
from apps.api.app.core.database import get_db_session
from apps.api.app.domain.bi import (
    CompanyComparisonResult,
    CompanyProfile,
    CompanyProfileDetail,
    CompetitorRelationship,
    ExecutiveBrief,
    RiskComparisonResult,
    RiskSummary,
    TrendSummary,
)
from apps.api.app.integrations.chat_factory import build_chat_provider
from apps.api.app.integrations.embedding_factory import build_embedding_provider
from apps.api.app.repositories.bi_repository import BiRepository
from apps.api.app.repositories.retrieval_repository import RetrievalRepository
from apps.api.app.schemas.bi import (
    AddCompetitorRequest,
    CompareCompaniesRequest,
    CompareRisksRequest,
    CompanyComparisonResponse,
    CompanyProfileDetailResponse,
    CompanyProfileResponse,
    CompetitorRelationshipResponse,
    CreateCompanyProfileRequest,
    ExecutiveBriefRequest,
    ExecutiveBriefResponse,
    RiskComparisonResponse,
    RiskSummaryRequest,
    RiskSummaryResponse,
    TrendSummaryRequest,
    TrendSummaryResponse,
)
from apps.api.app.schemas.retrieval import CitationResponse
from apps.api.app.services.citation_service import CitationSelectionService
from apps.api.app.services.company_profile_service import CompanyProfileService
from apps.api.app.services.competitor_service import CompetitorService
from apps.api.app.services.context_assembly_service import ContextAssemblyService
from apps.api.app.services.executive_brief_service import ExecutiveBriefService
from apps.api.app.services.market_trend_service import MarketTrendService
from apps.api.app.services.prompt_service import GroundedPromptService
from apps.api.app.services.question_answering_service import QuestionAnsweringService
from apps.api.app.services.reranking_service import DefaultReranker
from apps.api.app.services.retrieval_service import RetrievalService
from apps.api.app.services.risk_tracking_service import RiskTrackingService


router = APIRouter(prefix="/v1/bi", tags=["business-intelligence"])


def get_bi_repository() -> BiRepository:
    return BiRepository()


def get_retrieval_repository() -> RetrievalRepository:
    return RetrievalRepository()


def get_retrieval_service(
    request: Request,
    retrieval_repository: RetrievalRepository = Depends(get_retrieval_repository),
) -> RetrievalService:
    settings = get_request_settings(request)
    return RetrievalService(
        retrieval_repository=retrieval_repository,
        embedding_provider=build_embedding_provider(settings),
        reranker=DefaultReranker(),
        citation_selector=CitationSelectionService(),
    )


def get_question_answering_service(
    request: Request,
    retrieval_repository: RetrievalRepository = Depends(get_retrieval_repository),
) -> QuestionAnsweringService:
    settings = get_request_settings(request)
    retrieval_service = RetrievalService(
        retrieval_repository=retrieval_repository,
        embedding_provider=build_embedding_provider(settings),
        reranker=DefaultReranker(),
        citation_selector=CitationSelectionService(),
    )
    return QuestionAnsweringService(
        retrieval_service=retrieval_service,
        context_assembly_service=ContextAssemblyService(),
        prompt_service=GroundedPromptService(),
        chat_provider=build_chat_provider(settings),
    )


def get_company_profile_service(
    bi_repository: BiRepository = Depends(get_bi_repository),
) -> CompanyProfileService:
    return CompanyProfileService(bi_repository=bi_repository)


def get_competitor_service(
    bi_repository: BiRepository = Depends(get_bi_repository),
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
) -> CompetitorService:
    return CompetitorService(
        bi_repository=bi_repository,
        retrieval_service=retrieval_service,
    )


def get_risk_tracking_service(
    bi_repository: BiRepository = Depends(get_bi_repository),
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
) -> RiskTrackingService:
    return RiskTrackingService(
        bi_repository=bi_repository,
        retrieval_service=retrieval_service,
    )


def get_market_trend_service(
    bi_repository: BiRepository = Depends(get_bi_repository),
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
) -> MarketTrendService:
    return MarketTrendService(
        bi_repository=bi_repository,
        retrieval_service=retrieval_service,
    )


def get_executive_brief_service(
    bi_repository: BiRepository = Depends(get_bi_repository),
    question_answering_service: QuestionAnsweringService = Depends(get_question_answering_service),
) -> ExecutiveBriefService:
    return ExecutiveBriefService(
        bi_repository=bi_repository,
        question_answering_service=question_answering_service,
    )


@router.post("/companies", response_model=CompanyProfileResponse, status_code=201)
async def create_company_profile(
    payload: CreateCompanyProfileRequest,
    session: AsyncSession = Depends(get_db_session),
    company_profile_service: CompanyProfileService = Depends(get_company_profile_service),
) -> CompanyProfileResponse:
    profile = await company_profile_service.create_company_profile(
        session,
        name=payload.name,
        display_name=payload.display_name,
        industry=payload.industry,
        description=payload.description,
        metadata=payload.metadata,
    )
    return _to_company_profile_response(profile)


@router.get("/companies", response_model=list[CompanyProfileResponse])
async def list_company_profiles(
    session: AsyncSession = Depends(get_db_session),
    company_profile_service: CompanyProfileService = Depends(get_company_profile_service),
) -> list[CompanyProfileResponse]:
    profiles = await company_profile_service.list_company_profiles(session)
    return [_to_company_profile_response(profile) for profile in profiles]


@router.get("/companies/{company_id}", response_model=CompanyProfileDetailResponse)
async def get_company_profile(
    company_id: str,
    session: AsyncSession = Depends(get_db_session),
    company_profile_service: CompanyProfileService = Depends(get_company_profile_service),
) -> CompanyProfileDetailResponse:
    detail = await company_profile_service.get_company_profile(session, company_id=company_id)
    return _to_company_profile_detail_response(detail)


@router.post("/companies/{company_id}/competitors", response_model=CompetitorRelationshipResponse)
async def add_competitor(
    company_id: str,
    payload: AddCompetitorRequest,
    session: AsyncSession = Depends(get_db_session),
    competitor_service: CompetitorService = Depends(get_competitor_service),
) -> CompetitorRelationshipResponse:
    relationship = await competitor_service.add_competitor(
        session,
        company_id=company_id,
        competitor_company_id=payload.competitor_company_id,
        relationship_type=payload.relationship_type,
        notes=payload.notes,
    )
    return _to_competitor_relationship_response(relationship)


@router.get("/companies/{company_id}/competitors", response_model=list[CompetitorRelationshipResponse])
async def list_competitors(
    company_id: str,
    session: AsyncSession = Depends(get_db_session),
    competitor_service: CompetitorService = Depends(get_competitor_service),
) -> list[CompetitorRelationshipResponse]:
    relationships = await competitor_service.list_competitors(session, company_id=company_id)
    return [_to_competitor_relationship_response(relationship) for relationship in relationships]


@router.post("/companies/compare", response_model=CompanyComparisonResponse)
async def compare_companies(
    payload: CompareCompaniesRequest,
    session: AsyncSession = Depends(get_db_session),
    competitor_service: CompetitorService = Depends(get_competitor_service),
) -> CompanyComparisonResponse:
    result = await competitor_service.compare_companies(
        session,
        company_ids=payload.company_ids,
        query=payload.query,
        mode=payload.mode,
        top_k=payload.top_k,
    )
    return _to_company_comparison_response(result)


@router.post("/companies/{company_id}/risks/summarize", response_model=RiskSummaryResponse)
async def summarize_risks(
    company_id: str,
    payload: RiskSummaryRequest,
    session: AsyncSession = Depends(get_db_session),
    risk_tracking_service: RiskTrackingService = Depends(get_risk_tracking_service),
) -> RiskSummaryResponse:
    summary = await risk_tracking_service.summarize_risks(
        session,
        company_id=company_id,
        refresh=payload.refresh,
        mode=payload.mode,
        top_k=payload.top_k,
    )
    return _to_risk_summary_response(summary)


@router.post("/risks/compare", response_model=RiskComparisonResponse)
async def compare_risks(
    payload: CompareRisksRequest,
    session: AsyncSession = Depends(get_db_session),
    risk_tracking_service: RiskTrackingService = Depends(get_risk_tracking_service),
) -> RiskComparisonResponse:
    result = await risk_tracking_service.compare_risks(
        session,
        company_ids=payload.company_ids,
        refresh=payload.refresh,
        mode=payload.mode,
        top_k=payload.top_k,
    )
    return _to_risk_comparison_response(result)


@router.post("/trends/summarize", response_model=TrendSummaryResponse)
async def summarize_market_trends(
    payload: TrendSummaryRequest,
    session: AsyncSession = Depends(get_db_session),
    market_trend_service: MarketTrendService = Depends(get_market_trend_service),
) -> TrendSummaryResponse:
    summary = await market_trend_service.summarize_trends(
        session,
        company_id=payload.company_id,
        document_type=payload.document_type,
        date_from=payload.date_from,
        date_to=payload.date_to,
        refresh=payload.refresh,
        mode=payload.mode,
        top_k=payload.top_k,
    )
    return _to_trend_summary_response(summary)


@router.post("/briefs/executive", response_model=ExecutiveBriefResponse)
async def generate_executive_brief(
    payload: ExecutiveBriefRequest,
    session: AsyncSession = Depends(get_db_session),
    executive_brief_service: ExecutiveBriefService = Depends(get_executive_brief_service),
) -> ExecutiveBriefResponse:
    brief = await executive_brief_service.generate_executive_brief(
        session,
        topic=payload.topic,
        company_id=payload.company_id,
        mode=payload.mode,
        top_k=payload.top_k,
    )
    return _to_executive_brief_response(brief)


def _to_company_profile_response(profile: CompanyProfile) -> CompanyProfileResponse:
    return CompanyProfileResponse(
        company_id=profile.company_id,
        name=profile.name,
        display_name=profile.display_name,
        industry=profile.industry,
        description=profile.description,
        metadata=profile.metadata,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def _to_company_profile_detail_response(detail: CompanyProfileDetail) -> CompanyProfileDetailResponse:
    return CompanyProfileDetailResponse(
        **_to_company_profile_response(detail.profile).model_dump(),
        document_count=detail.document_count,
        documents_by_type=detail.documents_by_type,
        total_chunks=detail.total_chunks,
        indexed_document_count=detail.indexed_document_count,
        documents=[
            {
                "document_id": document.document_id,
                "title": document.title,
                "document_type": document.document_type,
                "source": document.source,
                "document_date": document.document_date,
                "indexing_status": document.indexing_status,
                "chunk_count": document.chunk_count,
            }
            for document in detail.documents
        ],
    )


def _to_competitor_relationship_response(
    relationship: CompetitorRelationship,
) -> CompetitorRelationshipResponse:
    return CompetitorRelationshipResponse(
        relationship_id=relationship.relationship_id,
        company_id=relationship.company_id,
        competitor_company_id=relationship.competitor_company_id,
        competitor_name=relationship.competitor_name,
        relationship_type=relationship.relationship_type,
        notes=relationship.notes,
        created_at=relationship.created_at,
    )


def _to_citation_response(citation) -> CitationResponse:
    return CitationResponse(
        document_id=citation.document_id,
        title=citation.title,
        chunk_id=citation.chunk_id,
        page_number=citation.page_number,
        score=citation.score,
        snippet=citation.snippet,
    )


def _to_company_comparison_response(result: CompanyComparisonResult) -> CompanyComparisonResponse:
    return CompanyComparisonResponse(
        companies=[
            {
                "company_id": metric.company_id,
                "company_name": metric.company_name,
                "document_count": metric.document_count,
                "total_chunks": metric.total_chunks,
                "indexed_document_count": metric.indexed_document_count,
                "top_document_types": metric.top_document_types,
                "evidence_snippets": metric.evidence_snippets,
            }
            for metric in result.companies
        ],
        comparison_query=result.comparison_query,
        shared_topics=result.shared_topics,
        citations=[_to_citation_response(citation) for citation in result.citations],
    )


def _to_risk_summary_response(summary: RiskSummary) -> RiskSummaryResponse:
    return RiskSummaryResponse(
        company_id=summary.company_id,
        company_name=summary.company_name,
        total_evidence_count=summary.total_evidence_count,
        categories=[
            {
                "category": category.category,
                "count": category.count,
                "top_snippets": category.top_snippets,
                "average_score": category.average_score,
            }
            for category in summary.categories
        ],
        citations=[_to_citation_response(citation) for citation in summary.citations],
        evidence_available=summary.evidence_available,
    )


def _to_risk_comparison_response(result: RiskComparisonResult) -> RiskComparisonResponse:
    return RiskComparisonResponse(
        companies=[_to_risk_summary_response(summary) for summary in result.companies],
        shared_categories=result.shared_categories,
        unique_categories_by_company=result.unique_categories_by_company,
    )


def _to_trend_summary_response(summary: TrendSummary) -> TrendSummaryResponse:
    return TrendSummaryResponse(
        company_id=summary.company_id,
        company_name=summary.company_name,
        document_type=summary.document_type,
        date_from=summary.date_from,
        date_to=summary.date_to,
        total_evidence_count=summary.total_evidence_count,
        topics=[
            {
                "topic": topic.topic,
                "count": topic.count,
                "document_types": topic.document_types,
                "top_snippets": topic.top_snippets,
                "average_score": topic.average_score,
            }
            for topic in summary.topics
        ],
        citations=[_to_citation_response(citation) for citation in summary.citations],
        evidence_available=summary.evidence_available,
    )


def _to_executive_brief_response(brief: ExecutiveBrief) -> ExecutiveBriefResponse:
    return ExecutiveBriefResponse(
        title=brief.title,
        summary=brief.summary,
        key_points=brief.key_points,
        citations=[_to_citation_response(citation) for citation in brief.citations],
        confidence=brief.confidence,
        human_review_recommended=brief.human_review_recommended,
        llm_provider=brief.llm_provider,
        llm_model=brief.llm_model,
        company_id=brief.company_id,
        company_name=brief.company_name,
        topic=brief.topic,
    )

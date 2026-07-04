from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.core.config import get_request_settings
from apps.api.app.core.database import get_db_session
from apps.api.app.domain.retrieval import RetrievalFilters
from apps.api.app.integrations.chat_factory import build_chat_provider
from apps.api.app.integrations.embedding_factory import build_embedding_provider
from apps.api.app.repositories.retrieval_repository import RetrievalRepository
from apps.api.app.schemas.retrieval import (
    AskQuestionAcrossDocumentsRequest,
    AskQuestionRequest,
    CitationResponse,
    ContextPreviewResponse,
    RetrievedChunkResponse,
    SearchRequest,
    SearchResponse,
    QuestionAnswerResponse,
)
from apps.api.app.services.citation_service import CitationSelectionService
from apps.api.app.services.context_assembly_service import ContextAssemblyService
from apps.api.app.services.prompt_service import GroundedPromptService
from apps.api.app.services.question_answering_service import QuestionAnsweringService
from apps.api.app.services.reranking_service import DefaultReranker
from apps.api.app.services.retrieval_service import RetrievalService


router = APIRouter(tags=["retrieval", "qa"])


def get_retrieval_repository() -> RetrievalRepository:
    return RetrievalRepository()


def get_retrieval_service(
    request: Request,
    retrieval_repository: RetrievalRepository = Depends(get_retrieval_repository),
) -> RetrievalService:
    settings = get_request_settings(request)
    embedding_provider = build_embedding_provider(settings)
    return RetrievalService(
        retrieval_repository=retrieval_repository,
        embedding_provider=embedding_provider,
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


@router.post("/v1/retrieval/search", response_model=SearchResponse)
async def search_documents(
    payload: SearchRequest,
    session: AsyncSession = Depends(get_db_session),
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
) -> SearchResponse:
    retrieval_result = await retrieval_service.retrieve(
        session,
        query=payload.query,
        mode=payload.mode,
        filters=_to_filters(payload.filters),
        top_k=payload.top_k,
    )
    return _to_search_response(retrieval_result)


@router.post("/v1/retrieval/context-preview", response_model=ContextPreviewResponse)
async def preview_retrieved_context(
    payload: SearchRequest,
    session: AsyncSession = Depends(get_db_session),
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
) -> ContextPreviewResponse:
    retrieval_result = await retrieval_service.retrieve(
        session,
        query=payload.query,
        mode=payload.mode,
        filters=_to_filters(payload.filters),
        top_k=payload.top_k,
    )
    assembled = ContextAssemblyService().assemble(
        chunks=retrieval_result.chunks,
        citations=retrieval_result.citations,
    )
    return ContextPreviewResponse(
        mode=retrieval_result.mode,
        query=retrieval_result.query,
        context=assembled.text,
        chunk_count=assembled.chunk_count,
        truncated=assembled.truncated,
        citations=[_to_citation_response(citation) for citation in assembled.citations],
    )


@router.post("/v1/qa/ask", response_model=QuestionAnswerResponse)
async def ask_question(
    payload: AskQuestionRequest,
    session: AsyncSession = Depends(get_db_session),
    qa_service: QuestionAnsweringService = Depends(get_question_answering_service),
) -> QuestionAnswerResponse:
    result = await qa_service.answer(
        session,
        question=payload.query,
        mode=payload.mode,
        filters=_to_filters(payload.filters),
        top_k=payload.top_k,
    )
    return _to_question_answer_response(result)


@router.post("/v1/qa/ask/document/{document_id}", response_model=QuestionAnswerResponse)
async def ask_question_within_document(
    document_id: str,
    payload: AskQuestionRequest,
    session: AsyncSession = Depends(get_db_session),
    qa_service: QuestionAnsweringService = Depends(get_question_answering_service),
) -> QuestionAnswerResponse:
    filters = _to_filters(payload.filters)
    filters = RetrievalFilters(
        **{
            **filters.__dict__,
            "document_ids": [document_id],
        }
    )
    result = await qa_service.answer(
        session,
        question=payload.query,
        mode=payload.mode,
        filters=filters,
        top_k=payload.top_k,
    )
    return _to_question_answer_response(result)


@router.post("/v1/qa/ask/documents", response_model=QuestionAnswerResponse)
async def ask_question_across_documents(
    payload: AskQuestionAcrossDocumentsRequest,
    session: AsyncSession = Depends(get_db_session),
    qa_service: QuestionAnsweringService = Depends(get_question_answering_service),
) -> QuestionAnswerResponse:
    filters = _to_filters(payload.filters)
    filters = RetrievalFilters(
        **{
            **filters.__dict__,
            "document_ids": payload.document_ids,
        }
    )
    result = await qa_service.answer(
        session,
        question=payload.query,
        mode=payload.mode,
        filters=filters,
        top_k=payload.top_k,
    )
    return _to_question_answer_response(result)


def _to_filters(payload) -> RetrievalFilters:
    return RetrievalFilters(**payload.model_dump())


def _to_search_response(result) -> SearchResponse:
    return SearchResponse(
        mode=result.mode,
        query=result.query,
        total_candidates=result.total_candidates,
        chunks=[
            RetrievedChunkResponse(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                document_title=chunk.document_title,
                text=chunk.text,
                score=chunk.score,
                semantic_score=chunk.semantic_score,
                keyword_score=chunk.keyword_score,
                rerank_score=chunk.rerank_score,
                page_number=chunk.page_number,
                document_metadata=chunk.document_metadata,
                chunk_metadata=chunk.chunk_metadata,
            )
            for chunk in result.chunks
        ],
        citations=[_to_citation_response(citation) for citation in result.citations],
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


def _to_question_answer_response(result) -> QuestionAnswerResponse:
    return QuestionAnswerResponse(
        answer=result.answer,
        confidence=result.confidence,
        llm_provider=result.llm_provider,
        llm_model=result.llm_model,
        finish_reason=result.finish_reason,
        retrieval=_to_search_response(result.retrieval),
        citations=[_to_citation_response(citation) for citation in result.citations],
        context_preview=result.context.text,
    )

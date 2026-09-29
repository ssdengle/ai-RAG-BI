from __future__ import annotations

from fastapi import Request

from apps.api.app.core.config import get_request_settings
from apps.api.app.core.platform import get_cache_client
from apps.api.app.integrations.caching.qa_cache import CachingQuestionAnsweringService
from apps.api.app.integrations.caching.retrieval_cache import CachingRetrievalService
from apps.api.app.integrations.caching.workflow_cache import CachingWorkflowService
from apps.api.app.integrations.chat_factory import build_chat_provider
from apps.api.app.integrations.embedding_factory import build_embedding_provider
from apps.api.app.repositories.retrieval_repository import RetrievalRepository
from apps.api.app.repositories.workflow_repository import WorkflowRepository
from apps.api.app.services.citation_service import CitationSelectionService
from apps.api.app.services.context_assembly_service import ContextAssemblyService
from apps.api.app.services.prompt_service import GroundedPromptService
from apps.api.app.services.question_answering_service import QuestionAnsweringService
from apps.api.app.services.reranking_service import DefaultReranker
from apps.api.app.services.retrieval_service import RetrievalService
from apps.api.app.services.workflow_service import WorkflowService
from apps.api.app.workflows.orchestrator import WorkflowOrchestrator


def build_retrieval_service(request: Request, retrieval_repository: RetrievalRepository) -> RetrievalService:
    settings = get_request_settings(request)
    cache_client = get_cache_client(request)
    service = RetrievalService(
        retrieval_repository=retrieval_repository,
        embedding_provider=build_embedding_provider(settings, cache_client=cache_client),
        reranker=DefaultReranker(),
        citation_selector=CitationSelectionService(),
    )
    if settings.cache.enabled:
        return CachingRetrievalService(service, cache_client, settings.cache)
    return service


def build_question_answering_service(request: Request, retrieval_repository: RetrievalRepository) -> QuestionAnsweringService:
    settings = get_request_settings(request)
    cache_client = get_cache_client(request)
    service = QuestionAnsweringService(
        retrieval_service=build_retrieval_service(request, retrieval_repository),
        context_assembly_service=ContextAssemblyService(),
        prompt_service=GroundedPromptService(),
        chat_provider=build_chat_provider(settings),
    )
    if settings.cache.enabled:
        return CachingQuestionAnsweringService(service, cache_client, settings.cache)
    return service


def build_workflow_service(
    request: Request,
    *,
    workflow_repository: WorkflowRepository,
    orchestrator: WorkflowOrchestrator,
    runtime_factory,
) -> WorkflowService:
    settings = get_request_settings(request)
    cache_client = get_cache_client(request)
    service = WorkflowService(
        workflow_repository=workflow_repository,
        orchestrator=orchestrator,
        runtime_factory=runtime_factory,
    )
    if settings.cache.enabled:
        return CachingWorkflowService(service, cache_client, settings.cache)
    return service

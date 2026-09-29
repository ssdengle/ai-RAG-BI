from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.agents.runtime import WorkflowRuntimeContext
from apps.api.app.api.bi import (
    get_company_profile_service,
    get_competitor_service,
    get_executive_brief_service,
    get_market_trend_service,
    get_risk_tracking_service,
)
from apps.api.app.api.documents import get_knowledge_base_service
from apps.api.app.api.qa import get_question_answering_service, get_retrieval_service
from apps.api.app.core.database import get_db_session
from apps.api.app.core.service_factory import build_workflow_service
from apps.api.app.domain.workflows import WorkflowRun
from apps.api.app.repositories.workflow_repository import WorkflowRepository
from apps.api.app.schemas.workflows import (
    RunWorkflowRequest,
    WorkflowResponse,
    WorkflowStateResponse,
    WorkflowTraceEventResponse,
    WorkflowTraceResponse,
)
from apps.api.app.services.workflow_service import WorkflowService
from apps.api.app.workflows.orchestrator import WorkflowOrchestrator


router = APIRouter(prefix="/v1/workflows", tags=["workflows"])


def get_workflow_repository() -> WorkflowRepository:
    return WorkflowRepository()


def get_workflow_orchestrator(
    workflow_repository: WorkflowRepository = Depends(get_workflow_repository),
) -> WorkflowOrchestrator:
    return WorkflowOrchestrator(workflow_repository=workflow_repository)


def get_workflow_service(
    request: Request,
    workflow_repository: WorkflowRepository = Depends(get_workflow_repository),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
    retrieval_service=Depends(get_retrieval_service),
    question_answering_service=Depends(get_question_answering_service),
    knowledge_base_service=Depends(get_knowledge_base_service),
    company_profile_service=Depends(get_company_profile_service),
    competitor_service=Depends(get_competitor_service),
    risk_tracking_service=Depends(get_risk_tracking_service),
    market_trend_service=Depends(get_market_trend_service),
    executive_brief_service=Depends(get_executive_brief_service),
) -> WorkflowService:
    def runtime_factory(session: AsyncSession) -> WorkflowRuntimeContext:
        return WorkflowRuntimeContext(
            session=session,
            retrieval_service=retrieval_service,
            question_answering_service=question_answering_service,
            knowledge_base_service=knowledge_base_service,
            company_profile_service=company_profile_service,
            competitor_service=competitor_service,
            risk_tracking_service=risk_tracking_service,
            market_trend_service=market_trend_service,
            executive_brief_service=executive_brief_service,
        )

    return build_workflow_service(
        request,
        workflow_repository=workflow_repository,
        orchestrator=orchestrator,
        runtime_factory=runtime_factory,
    )


@router.post("/run", response_model=WorkflowResponse, status_code=201)
async def run_workflow(
    payload: RunWorkflowRequest,
    session: AsyncSession = Depends(get_db_session),
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> WorkflowResponse:
    workflow = await workflow_service.run_workflow(
        session,
        user_request=payload.user_request,
        topic=payload.topic,
        company_id=payload.company_id,
        company_ids=payload.company_ids,
        max_retries=payload.max_retries,
    )
    return _to_workflow_response(workflow)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str,
    session: AsyncSession = Depends(get_db_session),
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> WorkflowResponse:
    workflow = await workflow_service.get_workflow(session, workflow_id=workflow_id)
    return _to_workflow_response(workflow)


@router.get("/{workflow_id}/state", response_model=WorkflowStateResponse)
async def get_workflow_state(
    workflow_id: str,
    session: AsyncSession = Depends(get_db_session),
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> WorkflowStateResponse:
    state = await workflow_service.get_workflow_state(session, workflow_id=workflow_id)
    workflow = await workflow_service.get_workflow(session, workflow_id=workflow_id)
    return WorkflowStateResponse(
        workflow_id=workflow_id,
        status=workflow.status.value,
        state=state,
    )


@router.get("/{workflow_id}/trace", response_model=WorkflowTraceResponse)
async def get_workflow_trace(
    workflow_id: str,
    session: AsyncSession = Depends(get_db_session),
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> WorkflowTraceResponse:
    trace = await workflow_service.get_workflow_trace(session, workflow_id=workflow_id)
    return WorkflowTraceResponse(
        workflow_id=workflow_id,
        trace=[WorkflowTraceEventResponse(**item) for item in trace],
    )


@router.post("/{workflow_id}/retry", response_model=WorkflowResponse)
async def retry_workflow(
    workflow_id: str,
    session: AsyncSession = Depends(get_db_session),
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> WorkflowResponse:
    workflow = await workflow_service.retry_workflow(session, workflow_id=workflow_id)
    return _to_workflow_response(workflow)


@router.post("/{workflow_id}/cancel", response_model=WorkflowResponse)
async def cancel_workflow(
    workflow_id: str,
    session: AsyncSession = Depends(get_db_session),
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> WorkflowResponse:
    workflow = await workflow_service.cancel_workflow(session, workflow_id=workflow_id)
    return _to_workflow_response(workflow)


def _to_workflow_response(workflow: WorkflowRun) -> WorkflowResponse:
    return WorkflowResponse(
        workflow_id=workflow.workflow_id,
        status=workflow.status.value,
        user_request=workflow.user_request,
        topic=workflow.topic,
        company_id=workflow.company_id,
        company_ids=workflow.company_ids,
        plan=workflow.plan,
        completed_steps=workflow.completed_steps,
        failed_steps=workflow.failed_steps,
        confidence=workflow.confidence,
        human_review_required=workflow.human_review_required,
        retry_count=workflow.retry_count,
        max_retries=workflow.max_retries,
        final_output=workflow.final_output,
        errors=workflow.errors,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        started_at=workflow.started_at,
        completed_at=workflow.completed_at,
    )

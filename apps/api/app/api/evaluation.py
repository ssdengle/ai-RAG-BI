from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.api.bi import get_executive_brief_service
from apps.api.app.api.qa import get_question_answering_service, get_retrieval_service
from apps.api.app.api.workflows import get_workflow_service
from apps.api.app.core.database import get_db_session
from apps.api.app.core.errors import DomainError
from apps.api.app.domain.evaluation import (
    DEFAULT_SCORERS,
    EvaluationResult,
    EvaluationRun,
    EvaluationTargetType,
    ExpectedAnswer,
    RunEvaluationConfig,
    ScoringRubric,
    SourceDocument,
)
from apps.api.app.repositories.evaluation_repository import EvaluationRepository
from apps.api.app.schemas.evaluation import (
    BenchmarkDatasetResponse,
    CreateBenchmarkDatasetRequest,
    CreateTestCaseRequest,
    EvaluationReportResponse,
    EvaluationResultResponse,
    EvaluationRunResponse,
    ExpectedAnswerRequest,
    FailedTestCaseResponse,
    ModelComparisonResponse,
    RegressionComparisonResponse,
    RunEvaluationRequest,
    ScorerResultResponse,
    ScoringRubricRequest,
    SourceDocumentRequest,
    TestCaseResponse,
)
from apps.api.app.services.evaluation_dataset_service import EvaluationDatasetService
from apps.api.app.services.evaluation_report_service import EvaluationReportService
from apps.api.app.services.evaluation_runner_service import EvaluationRunnerService


router = APIRouter(prefix="/v1/evaluation", tags=["evaluation"])


def get_evaluation_repository() -> EvaluationRepository:
    return EvaluationRepository()


def get_evaluation_dataset_service(
    evaluation_repository: EvaluationRepository = Depends(get_evaluation_repository),
) -> EvaluationDatasetService:
    return EvaluationDatasetService(evaluation_repository=evaluation_repository)


def get_evaluation_report_service(
    evaluation_repository: EvaluationRepository = Depends(get_evaluation_repository),
) -> EvaluationReportService:
    return EvaluationReportService(evaluation_repository=evaluation_repository)


def get_evaluation_runner_service(
    evaluation_repository: EvaluationRepository = Depends(get_evaluation_repository),
    retrieval_service=Depends(get_retrieval_service),
    question_answering_service=Depends(get_question_answering_service),
    executive_brief_service=Depends(get_executive_brief_service),
    workflow_service=Depends(get_workflow_service),
) -> EvaluationRunnerService:
    return EvaluationRunnerService(
        evaluation_repository=evaluation_repository,
        retrieval_service=retrieval_service,
        question_answering_service=question_answering_service,
        executive_brief_service=executive_brief_service,
        workflow_service=workflow_service,
    )


@router.post("/datasets", response_model=BenchmarkDatasetResponse, status_code=201)
async def create_benchmark_dataset(
    payload: CreateBenchmarkDatasetRequest,
    session: AsyncSession = Depends(get_db_session),
    dataset_service: EvaluationDatasetService = Depends(get_evaluation_dataset_service),
) -> BenchmarkDatasetResponse:
    dataset = await dataset_service.create_dataset(
        session,
        name=payload.name,
        description=payload.description,
        target_type=EvaluationTargetType(payload.target_type),
        version=payload.version,
        metadata=payload.metadata,
    )
    return _to_dataset_response(dataset)


@router.get("/datasets", response_model=list[BenchmarkDatasetResponse])
async def list_benchmark_datasets(
    session: AsyncSession = Depends(get_db_session),
    dataset_service: EvaluationDatasetService = Depends(get_evaluation_dataset_service),
) -> list[BenchmarkDatasetResponse]:
    datasets = await dataset_service.list_datasets(session)
    return [_to_dataset_response(dataset) for dataset in datasets]


@router.post("/datasets/{dataset_id}/test-cases", response_model=TestCaseResponse, status_code=201)
async def create_test_case(
    dataset_id: str,
    payload: CreateTestCaseRequest,
    session: AsyncSession = Depends(get_db_session),
    dataset_service: EvaluationDatasetService = Depends(get_evaluation_dataset_service),
) -> TestCaseResponse:
    test_case = await dataset_service.create_test_case(
        session,
        dataset_id=dataset_id,
        name=payload.name,
        query=payload.query,
        expected_answer=_to_expected_answer(payload.expected_answer),
        source_documents=[_to_source_document(item) for item in payload.source_documents],
        rubric=_to_rubric(payload.rubric),
        input_payload=payload.input_payload,
        tags=payload.tags,
    )
    return _to_test_case_response(test_case)


@router.get("/datasets/{dataset_id}/test-cases", response_model=list[TestCaseResponse])
async def list_test_cases(
    dataset_id: str,
    session: AsyncSession = Depends(get_db_session),
    dataset_service: EvaluationDatasetService = Depends(get_evaluation_dataset_service),
) -> list[TestCaseResponse]:
    test_cases = await dataset_service.list_test_cases(session, dataset_id=dataset_id)
    return [_to_test_case_response(test_case) for test_case in test_cases]


@router.post("/datasets/{dataset_id}/runs", response_model=EvaluationRunResponse, status_code=201)
async def run_evaluation(
    dataset_id: str,
    payload: RunEvaluationRequest,
    session: AsyncSession = Depends(get_db_session),
    runner_service: EvaluationRunnerService = Depends(get_evaluation_runner_service),
) -> EvaluationRunResponse:
    config = RunEvaluationConfig(
        mode=payload.mode,
        top_k=payload.top_k,
        pass_threshold=payload.pass_threshold,
        enabled_scorers=payload.enabled_scorers or list(DEFAULT_SCORERS),
        latency_threshold_ms=payload.latency_threshold_ms,
        cost_threshold_usd=payload.cost_threshold_usd,
        company_id=payload.company_id,
        max_retries=payload.max_retries,
    )
    run = await runner_service.run_evaluation(
        session,
        dataset_id=dataset_id,
        config=config,
        baseline_run_id=payload.baseline_run_id,
    )
    return _to_run_response(run)


@router.get("/runs/{run_id}", response_model=EvaluationRunResponse)
async def get_evaluation_run(
    run_id: str,
    session: AsyncSession = Depends(get_db_session),
    evaluation_repository: EvaluationRepository = Depends(get_evaluation_repository),
) -> EvaluationRunResponse:
    run = await evaluation_repository.get_run(session, run_id)
    if run is None:
        raise DomainError(
            "Evaluation run was not found.",
            details=run_id,
            code="evaluation_run_not_found",
            status_code=404,
        )
    return _to_run_response(run)


@router.get("/runs/{run_id}/results", response_model=list[EvaluationResultResponse])
async def get_evaluation_results(
    run_id: str,
    session: AsyncSession = Depends(get_db_session),
    evaluation_repository: EvaluationRepository = Depends(get_evaluation_repository),
) -> list[EvaluationResultResponse]:
    run = await evaluation_repository.get_run(session, run_id)
    if run is None:
        raise DomainError(
            "Evaluation run was not found.",
            details=run_id,
            code="evaluation_run_not_found",
            status_code=404,
        )
    results = await evaluation_repository.list_results(session, run_id=run_id)
    return [_to_result_response(result) for result in results]


@router.get("/runs/{run_id}/report", response_model=EvaluationReportResponse)
async def get_evaluation_report(
    run_id: str,
    session: AsyncSession = Depends(get_db_session),
    report_service: EvaluationReportService = Depends(get_evaluation_report_service),
) -> EvaluationReportResponse:
    report = await report_service.generate_report(session, run_id=run_id)
    return _to_report_response(report)


def _to_expected_answer(payload: ExpectedAnswerRequest) -> ExpectedAnswer:
    return ExpectedAnswer(
        text=payload.text,
        required_citations=payload.required_citations,
        required_keywords=payload.required_keywords,
        min_confidence=payload.min_confidence,
    )


def _to_source_document(payload: SourceDocumentRequest) -> SourceDocument:
    return SourceDocument(
        document_id=payload.document_id,
        title=payload.title,
        chunk_ids=payload.chunk_ids,
    )


def _to_rubric(payload: ScoringRubricRequest) -> ScoringRubric:
    return ScoringRubric(
        pass_threshold=payload.pass_threshold,
        scorer_weights=payload.scorer_weights,
        scorer_thresholds=payload.scorer_thresholds,
        enabled_scorers=payload.enabled_scorers,
    )


def _to_dataset_response(dataset) -> BenchmarkDatasetResponse:
    return BenchmarkDatasetResponse(
        dataset_id=dataset.dataset_id,
        name=dataset.name,
        description=dataset.description,
        target_type=dataset.target_type.value,
        version=dataset.version,
        metadata=dataset.metadata,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
    )


def _to_test_case_response(test_case) -> TestCaseResponse:
    return TestCaseResponse(
        test_case_id=test_case.test_case_id,
        dataset_id=test_case.dataset_id,
        name=test_case.name,
        query=test_case.query,
        expected_answer=ExpectedAnswerRequest(
            text=test_case.expected_answer.text,
            required_citations=test_case.expected_answer.required_citations,
            required_keywords=test_case.expected_answer.required_keywords,
            min_confidence=test_case.expected_answer.min_confidence,
        ),
        source_documents=[
            SourceDocumentRequest(
                document_id=document.document_id,
                title=document.title,
                chunk_ids=document.chunk_ids,
            )
            for document in test_case.source_documents
        ],
        rubric=ScoringRubricRequest(
            pass_threshold=test_case.rubric.pass_threshold,
            scorer_weights=test_case.rubric.scorer_weights,
            scorer_thresholds=test_case.rubric.scorer_thresholds,
            enabled_scorers=test_case.rubric.enabled_scorers,
        ),
        input_payload=test_case.input_payload,
        tags=test_case.tags,
        created_at=test_case.created_at,
        updated_at=test_case.updated_at,
    )


def _to_run_response(run: EvaluationRun) -> EvaluationRunResponse:
    return EvaluationRunResponse(
        run_id=run.run_id,
        dataset_id=run.dataset_id,
        status=run.status.value,
        target_type=run.target_type.value,
        config=run.config,
        baseline_run_id=run.baseline_run_id,
        llm_provider=run.llm_provider,
        llm_model=run.llm_model,
        summary=run.summary,
        error_message=run.error_message,
        created_at=run.created_at,
        updated_at=run.updated_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


def _to_result_response(result: EvaluationResult) -> EvaluationResultResponse:
    return EvaluationResultResponse(
        result_id=result.result_id,
        run_id=result.run_id,
        test_case_id=result.test_case_id,
        test_case_name=result.test_case_name,
        passed=result.passed,
        overall_score=result.overall_score,
        scorer_results=[
            ScorerResultResponse(
                scorer=item.scorer,
                score=item.score,
                passed=item.passed,
                details=item.details,
            )
            for item in result.scorer_results
        ],
        failure_modes=[mode.value for mode in result.failure_modes],
        actual_output=result.actual_output,
        latency_ms=result.latency_ms,
        token_usage=result.token_usage,
        error_message=result.error_message,
        created_at=result.created_at,
    )


def _to_report_response(report) -> EvaluationReportResponse:
    return EvaluationReportResponse(
        run_id=report.run_id,
        dataset_id=report.dataset_id,
        dataset_name=report.dataset_name,
        target_type=report.target_type.value,
        status=report.status.value,
        passed=report.passed,
        average_score=report.average_score,
        pass_rate=report.pass_rate,
        total_test_cases=report.total_test_cases,
        passed_test_cases=report.passed_test_cases,
        failed_test_cases=[
            FailedTestCaseResponse(
                test_case_id=item.test_case_id,
                test_case_name=item.test_case_name,
                overall_score=item.overall_score,
                failure_modes=item.failure_modes,
                error_message=item.error_message,
            )
            for item in report.failed_test_cases
        ],
        failure_mode_summary=report.failure_mode_summary,
        model_comparison=ModelComparisonResponse(
            provider=report.model_comparison.provider,
            model=report.model_comparison.model,
            average_score=report.model_comparison.average_score,
            pass_rate=report.model_comparison.pass_rate,
            total_test_cases=report.model_comparison.total_test_cases,
        ),
        regression_comparison=RegressionComparisonResponse(
            baseline_run_id=report.regression_comparison.baseline_run_id,
            current_average_score=report.regression_comparison.current_average_score,
            baseline_average_score=report.regression_comparison.baseline_average_score,
            score_delta=report.regression_comparison.score_delta,
            pass_rate_delta=report.regression_comparison.pass_rate_delta,
            regressed_test_cases=report.regression_comparison.regressed_test_cases,
        ),
        scorer_averages=report.scorer_averages,
        created_at=report.created_at,
        completed_at=report.completed_at,
    )

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from apps.api.app.api.evaluation import (
    get_evaluation_dataset_service,
    get_evaluation_report_service,
    get_evaluation_runner_service,
)
from apps.api.app.core.database import get_db_session
from apps.api.app.domain.evaluation import (
    BenchmarkDataset,
    EvaluationReport,
    EvaluationResult,
    EvaluationRun,
    EvaluationRunStatus,
    EvaluationTargetType,
    EvaluationTestCase,
    ExpectedAnswer,
    FailureMode,
    ModelComparisonField,
    RegressionComparisonField,
    ScorerResult,
    ScoringRubric,
)
from apps.api.app.main import create_app
from apps.api.tests.conftest import FakeDatabaseManager, FakeRedisManager, build_test_settings


NOW = datetime.now(timezone.utc)


class _FakeDatasetService:
    def __init__(self) -> None:
        self.datasets: list[BenchmarkDataset] = []
        self.test_cases: dict[str, list[EvaluationTestCase]] = {}

    async def create_dataset(self, session, *, name, description, target_type, version="1.0", metadata=None):
        dataset = BenchmarkDataset(
            dataset_id="dataset-1",
            name=name,
            description=description,
            target_type=target_type,
            version=version,
            metadata=metadata or {},
            created_at=NOW,
            updated_at=NOW,
        )
        self.datasets.append(dataset)
        self.test_cases.setdefault(dataset.dataset_id, [])
        return dataset

    async def list_datasets(self, session):
        return self.datasets

    async def get_dataset(self, session, *, dataset_id):
        for dataset in self.datasets:
            if dataset.dataset_id == dataset_id:
                return dataset
        from apps.api.app.core.errors import DomainError

        raise DomainError("Benchmark dataset was not found.", details=dataset_id, code="dataset_not_found", status_code=404)

    async def create_test_case(
        self,
        session,
        *,
        dataset_id,
        name,
        query,
        expected_answer,
        source_documents=None,
        rubric=None,
        input_payload=None,
        tags=None,
    ):
        test_case = EvaluationTestCase(
            test_case_id="tc-1",
            dataset_id=dataset_id,
            name=name,
            query=query,
            input_payload=input_payload or {},
            expected_answer=expected_answer,
            source_documents=source_documents or [],
            rubric=rubric or ScoringRubric(),
            tags=tags or [],
            created_at=NOW,
            updated_at=NOW,
        )
        self.test_cases.setdefault(dataset_id, []).append(test_case)
        return test_case

    async def list_test_cases(self, session, *, dataset_id):
        return self.test_cases.get(dataset_id, [])


class _FakeRunnerService:
    def __init__(self) -> None:
        self.run = EvaluationRun(
            run_id="run-1",
            dataset_id="dataset-1",
            status=EvaluationRunStatus.COMPLETED,
            target_type=EvaluationTargetType.GROUNDED_QA,
            config={"pass_threshold": 0.7},
            baseline_run_id=None,
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            summary={
                "total_test_cases": 0,
                "passed_test_cases": 0,
                "failed_test_cases": 0,
                "average_score": 0.0,
                "pass_rate": 0.0,
                "failure_mode_summary": {},
            },
            error_message=None,
            created_at=NOW,
            updated_at=NOW,
            started_at=NOW,
            completed_at=NOW,
        )

    async def run_evaluation(self, session, *, dataset_id, config=None, baseline_run_id=None):
        return self.run


class _FakeReportService:
    async def generate_report(self, session, *, run_id):
        return EvaluationReport(
            run_id=run_id,
            dataset_id="dataset-1",
            dataset_name="QA Benchmark",
            target_type=EvaluationTargetType.GROUNDED_QA,
            status=EvaluationRunStatus.COMPLETED,
            passed=True,
            average_score=0.0,
            pass_rate=0.0,
            total_test_cases=0,
            passed_test_cases=0,
            failed_test_cases=[],
            failure_mode_summary={},
            model_comparison=ModelComparisonField(
                provider="openai",
                model="gpt-4o-mini",
                average_score=0.0,
                pass_rate=0.0,
                total_test_cases=0,
            ),
            regression_comparison=RegressionComparisonField(
                baseline_run_id=None,
                current_average_score=0.0,
                baseline_average_score=None,
                score_delta=None,
                pass_rate_delta=None,
                regressed_test_cases=[],
            ),
            scorer_averages={},
            created_at=NOW,
            completed_at=NOW,
        )


class _FakeEvaluationRepository:
    def __init__(self) -> None:
        self.run = _FakeRunnerService().run
        self.results: list[EvaluationResult] = []

    async def get_run(self, session, run_id):
        if run_id == self.run.run_id:
            return self.run
        return None

    async def list_results(self, session, *, run_id):
        return self.results


async def _override_db_session():
    yield None


def _build_test_app():
    dataset_service = _FakeDatasetService()
    runner_service = _FakeRunnerService()
    report_service = _FakeReportService()
    repository = _FakeEvaluationRepository()

    app = create_app(
        settings=build_test_settings(),
        database_manager=FakeDatabaseManager(),
        redis_manager=FakeRedisManager(),
        perform_startup_checks=False,
    )
    app.dependency_overrides[get_db_session] = _override_db_session
    app.dependency_overrides[get_evaluation_dataset_service] = lambda: dataset_service
    app.dependency_overrides[get_evaluation_runner_service] = lambda: runner_service
    app.dependency_overrides[get_evaluation_report_service] = lambda: report_service
    from apps.api.app.api.evaluation import get_evaluation_repository

    app.dependency_overrides[get_evaluation_repository] = lambda: repository
    return app, dataset_service, runner_service, repository


def test_create_and_list_benchmark_datasets() -> None:
    with TestClient(_build_test_app()[0]) as client:
        create_response = client.post(
            "/v1/evaluation/datasets",
            json={
                "name": "QA Benchmark",
                "description": "Grounded Q&A cases",
                "target_type": "grounded_qa",
            },
        )
        list_response = client.get("/v1/evaluation/datasets")

    assert create_response.status_code == 201
    assert create_response.json()["name"] == "QA Benchmark"
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_create_and_list_test_cases() -> None:
    app, dataset_service, _, _ = _build_test_app()
    with TestClient(app) as client:
        client.post(
            "/v1/evaluation/datasets",
            json={"name": "QA Benchmark", "description": "", "target_type": "grounded_qa"},
        )
        create_response = client.post(
            "/v1/evaluation/datasets/dataset-1/test-cases",
            json={
                "name": "Revenue case",
                "query": "What happened to revenue?",
                "expected_answer": {
                    "text": "Revenue increased steadily.",
                    "required_citations": ["chunk-1"],
                },
            },
        )
        list_response = client.get("/v1/evaluation/datasets/dataset-1/test-cases")

    assert create_response.status_code == 201
    assert create_response.json()["query"] == "What happened to revenue?"
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_run_evaluation_and_fetch_run_results_report() -> None:
    app, _, _, repository = _build_test_app()
    repository.results.append(
        EvaluationResult(
            result_id="result-1",
            run_id="run-1",
            test_case_id="tc-1",
            test_case_name="Revenue case",
            passed=False,
            overall_score=0.0,
            scorer_results=[],
            failure_modes=[FailureMode.EMPTY_RESPONSE],
            actual_output={},
            latency_ms=None,
            token_usage={},
            error_message=None,
            created_at=NOW,
        )
    )

    with TestClient(app) as client:
        client.post(
            "/v1/evaluation/datasets",
            json={"name": "QA Benchmark", "description": "", "target_type": "grounded_qa"},
        )
        run_response = client.post("/v1/evaluation/datasets/dataset-1/runs", json={})
        get_run_response = client.get("/v1/evaluation/runs/run-1")
        results_response = client.get("/v1/evaluation/runs/run-1/results")
        report_response = client.get("/v1/evaluation/runs/run-1/report")

    assert run_response.status_code == 201
    assert run_response.json()["status"] == "completed"
    assert get_run_response.status_code == 200
    assert results_response.status_code == 200
    assert len(results_response.json()) == 1
    assert report_response.status_code == 200
    assert report_response.json()["dataset_name"] == "QA Benchmark"


def test_get_missing_run_returns_not_found() -> None:
    with TestClient(_build_test_app()[0]) as client:
        response = client.get("/v1/evaluation/runs/missing-run")

    assert response.status_code == 404
    assert response.json()["code"] == "evaluation_run_not_found"

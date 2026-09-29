from __future__ import annotations

from typing import Any, Optional

from apps.web.streamlit_app.api_client.base import BaseApiClient
from apps.web.streamlit_app.api_client.models import (
    BenchmarkDataset,
    EvaluationReport,
    EvaluationResult,
    EvaluationRun,
    TestCase,
)


class EvaluationApiClient:
    def __init__(self, client: BaseApiClient) -> None:
        self._client = client

    def list_datasets(self) -> list[BenchmarkDataset]:
        data = self._client.get_json("/v1/evaluation/datasets")
        return [BenchmarkDataset.model_validate(item) for item in data]

    def create_dataset(
        self,
        *,
        name: str,
        description: str = "",
        target_type: str,
        version: str = "1.0",
        metadata: Optional[dict[str, Any]] = None,
    ) -> BenchmarkDataset:
        payload = {
            "name": name,
            "description": description,
            "target_type": target_type,
            "version": version,
            "metadata": metadata or {},
        }
        data = self._client.post_json("/v1/evaluation/datasets", json=payload)
        return BenchmarkDataset.model_validate(data)

    def list_test_cases(self, dataset_id: str) -> list[TestCase]:
        data = self._client.get_json(f"/v1/evaluation/datasets/{dataset_id}/test-cases")
        return [TestCase.model_validate(item) for item in data]

    def create_test_case(
        self,
        dataset_id: str,
        *,
        name: str,
        query: str,
        expected_answer: dict[str, Any],
        source_documents: Optional[list[dict[str, Any]]] = None,
        rubric: Optional[dict[str, Any]] = None,
        input_payload: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
    ) -> TestCase:
        payload = {
            "name": name,
            "query": query,
            "expected_answer": expected_answer,
            "source_documents": source_documents or [],
            "rubric": rubric or {},
            "input_payload": input_payload or {},
            "tags": tags or [],
        }
        data = self._client.post_json(f"/v1/evaluation/datasets/{dataset_id}/test-cases", json=payload)
        return TestCase.model_validate(data)

    def run_evaluation(
        self,
        dataset_id: str,
        *,
        pass_threshold: float = 0.7,
        mode: str = "hybrid",
        top_k: int = 5,
        enabled_scorers: Optional[list[str]] = None,
        baseline_run_id: Optional[str] = None,
        company_id: Optional[str] = None,
        max_retries: int = 2,
    ) -> EvaluationRun:
        payload: dict[str, Any] = {
            "pass_threshold": pass_threshold,
            "mode": mode,
            "top_k": top_k,
            "max_retries": max_retries,
        }
        if enabled_scorers:
            payload["enabled_scorers"] = enabled_scorers
        if baseline_run_id:
            payload["baseline_run_id"] = baseline_run_id
        if company_id:
            payload["company_id"] = company_id
        data = self._client.post_json(f"/v1/evaluation/datasets/{dataset_id}/runs", json=payload)
        return EvaluationRun.model_validate(data)

    def get_run(self, run_id: str) -> EvaluationRun:
        data = self._client.get_json(f"/v1/evaluation/runs/{run_id}")
        return EvaluationRun.model_validate(data)

    def get_results(self, run_id: str) -> list[EvaluationResult]:
        data = self._client.get_json(f"/v1/evaluation/runs/{run_id}/results")
        return [EvaluationResult.model_validate(item) for item in data]

    def get_report(self, run_id: str) -> EvaluationReport:
        data = self._client.get_json(f"/v1/evaluation/runs/{run_id}/report")
        return EvaluationReport.model_validate(data)

from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.app.core.config import MetricsSettings
from apps.api.app.main import create_app
from apps.api.tests.conftest import FakeDatabaseManager, FakeRedisManager, build_test_settings


def test_metrics_endpoint_exposes_prometheus_payload() -> None:
    settings = build_test_settings().model_copy(update={"metrics": MetricsSettings(enabled=True)})
    app = create_app(
        settings=settings,
        database_manager=FakeDatabaseManager(),
        redis_manager=FakeRedisManager(),
        perform_startup_checks=False,
    )
    with TestClient(app) as client:
        response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text


def test_openapi_includes_security_schemes_and_examples() -> None:
    app = create_app(
        settings=build_test_settings(),
        database_manager=FakeDatabaseManager(),
        redis_manager=FakeRedisManager(),
        perform_startup_checks=False,
    )
    with TestClient(app) as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "BearerAuth" in schema["components"]["securitySchemes"]
    assert "example" in schema["paths"]["/v1/qa/ask"]["post"]["requestBody"]["content"]["application/json"]

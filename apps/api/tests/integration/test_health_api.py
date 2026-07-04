from fastapi.testclient import TestClient

from apps.api.app.core.errors import InfrastructureError
from apps.api.app.main import create_app
from apps.api.tests.conftest import FakeDatabaseManager, FakeRedisManager


def test_liveness_endpoint_reports_process_health(test_settings) -> None:
    app = create_app(
        settings=test_settings,
        database_manager=FakeDatabaseManager(),
        redis_manager=FakeRedisManager(),
        perform_startup_checks=False,
    )

    with TestClient(app) as client:
        response = client.get("/v1/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_endpoint_reports_dependency_health(test_settings) -> None:
    app = create_app(
        settings=test_settings,
        database_manager=FakeDatabaseManager(),
        redis_manager=FakeRedisManager(),
        perform_startup_checks=False,
    )

    with TestClient(app) as client:
        response = client.get("/v1/health/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["checks"]["postgresql"]["status"] == "ok"
    assert payload["checks"]["redis"]["status"] == "ok"


def test_readiness_endpoint_returns_service_unavailable_when_dependency_fails(test_settings) -> None:
    app = create_app(
        settings=test_settings,
        database_manager=FakeDatabaseManager(
            health_error=InfrastructureError(
                "Database unavailable.",
                details="connection refused",
                code="database_unavailable",
            )
        ),
        redis_manager=FakeRedisManager(),
        perform_startup_checks=False,
    )

    with TestClient(app) as client:
        response = client.get("/v1/health/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["checks"]["postgresql"]["status"] == "error"

from fastapi import Query
from fastapi.testclient import TestClient

from apps.api.app.core.errors import DomainError
from apps.api.app.main import create_app
from apps.api.tests.conftest import FakeDatabaseManager, FakeRedisManager


def test_domain_errors_return_standardized_error_response(test_settings) -> None:
    app = create_app(
        settings=test_settings,
        database_manager=FakeDatabaseManager(),
        redis_manager=FakeRedisManager(),
        perform_startup_checks=False,
    )

    @app.get("/test/domain-error")
    def raise_domain_error() -> None:
        raise DomainError(
            "Document cannot be processed.",
            details="sample failure",
            code="document_processing_failed",
            status_code=409,
        )

    with TestClient(app) as client:
        response = client.get("/test/domain-error")

    assert response.status_code == 409
    payload = response.json()
    assert payload["code"] == "document_processing_failed"
    assert payload["message"] == "Document cannot be processed."
    assert "request_id" in payload


def test_request_validation_errors_return_standardized_error_response(test_settings) -> None:
    app = create_app(
        settings=test_settings,
        database_manager=FakeDatabaseManager(),
        redis_manager=FakeRedisManager(),
        perform_startup_checks=False,
    )

    @app.get("/test/request-validation")
    def validate_value(value: int = Query(...)) -> dict[str, int]:
        return {"value": value}

    with TestClient(app) as client:
        response = client.get("/test/request-validation", params={"value": "bad"})

    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == "validation_error"
    assert payload["message"] == "Request validation failed."


def test_unhandled_errors_return_standardized_error_response(test_settings) -> None:
    app = create_app(
        settings=test_settings,
        database_manager=FakeDatabaseManager(),
        redis_manager=FakeRedisManager(),
        perform_startup_checks=False,
    )

    @app.get("/test/unhandled-error")
    def raise_unhandled_error() -> None:
        raise RuntimeError("unexpected")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/test/unhandled-error")

    assert response.status_code == 500
    payload = response.json()
    assert payload["code"] == "internal_server_error"
    assert payload["message"] == "An unexpected error occurred."

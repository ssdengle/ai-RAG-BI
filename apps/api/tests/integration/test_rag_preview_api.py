from fastapi.testclient import TestClient

from apps.api.app.main import create_app
from apps.api.tests.conftest import FakeDatabaseManager, FakeRedisManager


def test_preview_ingestion_endpoint_returns_chunked_document() -> None:
    app = create_app(
        perform_startup_checks=False,
        database_manager=FakeDatabaseManager(),
        redis_manager=FakeRedisManager(),
    )
    with TestClient(app) as client:
        response = client.post(
            "/v1/rag/ingestion/preview",
            json={
                "filename": "analysis.md",
                "content_type": "text/markdown",
                "content": "# Strategy\n\nRevenue increased steadily.\n\nCustomer retention improved materially.",
                "strategy": "semantic",
                "max_chunk_size": 80,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["filename"] == "analysis.md"
    assert payload["metadata"]["title"] == "Strategy"
    assert payload["chunk_count"] >= 1
    assert payload["chunks"][0]["strategy"] == "semantic"


def test_preview_ingestion_endpoint_rejects_unsupported_file_type() -> None:
    app = create_app(
        perform_startup_checks=False,
        database_manager=FakeDatabaseManager(),
        redis_manager=FakeRedisManager(),
    )
    with TestClient(app) as client:
        response = client.post(
            "/v1/rag/ingestion/preview",
            json={
                "filename": "archive.csv",
                "content_type": "text/csv",
                "content": "a,b,c",
                "strategy": "recursive",
            },
        )

    assert response.status_code == 415

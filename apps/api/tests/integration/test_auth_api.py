from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.app.api.documents import get_knowledge_base_service
from apps.api.app.core.config import AuthSettings, SecuritySettings
from apps.api.app.core.database import get_db_session
from apps.api.app.main import create_app
from apps.api.tests.conftest import FakeDatabaseManager, FakeRedisManager, build_test_settings


class _FakeKnowledgeBaseService:
    async def browse_documents(self, session, *, query):
        from apps.api.app.domain.documents import DocumentBrowsePage

        return DocumentBrowsePage(items=[], total=0, page=query.page, page_size=query.page_size)


async def _override_db_session():
    yield None


def _build_auth_app():
    settings = build_test_settings()
    settings = settings.model_copy(
        update={
            "auth": AuthSettings(enabled=True),
            "security": SecuritySettings(rate_limit_enabled=False, block_prompt_injection=False),
        }
    )
    app = create_app(
        settings=settings,
        database_manager=FakeDatabaseManager(),
        redis_manager=FakeRedisManager(),
        perform_startup_checks=False,
    )
    app.dependency_overrides[get_db_session] = _override_db_session
    app.dependency_overrides[get_knowledge_base_service] = lambda: _FakeKnowledgeBaseService()
    return app


def test_protected_endpoint_requires_authentication() -> None:
    with TestClient(_build_auth_app()) as client:
        response = client.get("/v1/documents")
    assert response.status_code == 401
    assert response.json()["code"] == "missing_credentials"


def test_api_key_grants_viewer_access_to_read_endpoints() -> None:
    with TestClient(_build_auth_app()) as client:
        response = client.get("/v1/documents", headers={"X-API-Key": "viewer-key"})
    assert response.status_code == 200


def test_viewer_cannot_create_documents() -> None:
    with TestClient(_build_auth_app()) as client:
        response = client.post(
            "/v1/documents",
            headers={"X-API-Key": "viewer-key"},
            json={"filename": "analysis.txt", "content_base64": "UmV2ZW51ZQ=="},
        )
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_login_and_access_with_bearer_token() -> None:
    with TestClient(_build_auth_app()) as client:
        login_response = client.post(
            "/v1/auth/login",
            json={"username": "analyst", "password": "change-me"},
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        documents_response = client.get(
            "/v1/documents",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert documents_response.status_code == 200

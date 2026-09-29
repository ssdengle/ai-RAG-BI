from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from apps.web.streamlit_app.api_client.auth import AuthApiClient
from apps.web.streamlit_app.api_client.base import BaseApiClient
from apps.web.streamlit_app.api_client.exceptions import AuthenticationError, NotFoundError
from apps.web.streamlit_app.api_client.metrics import MetricsApiClient
from apps.web.streamlit_app.config import WebSettings


def _settings() -> WebSettings:
    return WebSettings(
        api_base_url="http://testserver",
        request_timeout_seconds=5,
        max_retries=0,
        retry_backoff_seconds=0.1,
    )


def test_login_returns_token_response() -> None:
    client = AuthApiClient(_settings())
    response = httpx.Response(
        200,
        json={
            "access_token": "access",
            "refresh_token": "refresh",
            "token_type": "bearer",
            "expires_in": 3600,
        },
        request=httpx.Request("POST", "http://testserver/v1/auth/login"),
    )
    with patch.object(client, "_request", return_value=response):
        tokens = client.login("analyst", "change-me")
    assert tokens.access_token == "access"
    assert tokens.refresh_token == "refresh"


def test_request_raises_authentication_error_on_401() -> None:
    client = BaseApiClient(_settings(), access_token="bad-token")
    response = httpx.Response(
        401,
        json={"code": "invalid_token", "message": "Token expired.", "details": None},
        request=httpx.Request("GET", "http://testserver/v1/documents"),
    )
    with patch("apps.web.streamlit_app.api_client.base.httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.request.return_value = response
        with pytest.raises(AuthenticationError):
            client._request("GET", "/v1/documents")


def test_request_raises_not_found_on_404() -> None:
    client = BaseApiClient(_settings(), access_token="token")
    response = httpx.Response(
        404,
        json={"code": "document_not_found", "message": "Document was not found.", "details": "doc-1"},
        request=httpx.Request("GET", "http://testserver/v1/documents/doc-1"),
    )
    with patch("apps.web.streamlit_app.api_client.base.httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.request.return_value = response
        with pytest.raises(NotFoundError):
            client._request("GET", "/v1/documents/doc-1")


def test_refresh_callback_is_used_on_401() -> None:
    settings = _settings()
    refresh = MagicMock(return_value="new-token")
    client = BaseApiClient(settings, access_token="old-token", refresh_callback=refresh)
    unauthorized = httpx.Response(
        401,
        json={"code": "token_expired", "message": "Expired", "details": None},
        request=httpx.Request("GET", "http://testserver/v1/documents"),
    )
    authorized = httpx.Response(
        200,
        json={"items": [], "total": 0, "page": 1, "page_size": 20, "total_pages": 0},
        request=httpx.Request("GET", "http://testserver/v1/documents"),
    )

    with patch("apps.web.streamlit_app.api_client.base.httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.request.side_effect = [unauthorized, authorized]
        refresh.return_value = "new-token"
        payload = client.get_json("/v1/documents")

    assert payload["total"] == 0
    refresh.assert_called_once()


def test_metrics_parser_summarizes_prometheus_text() -> None:
    client = MetricsApiClient(BaseApiClient(_settings()))
    text = """
# TYPE http_requests_total counter
http_requests_total{method="GET",path="/v1/documents",status="200"} 12
# TYPE cache_hits_total counter
cache_hits_total{namespace="qa"} 4
# TYPE cache_misses_total counter
cache_misses_total{namespace="qa"} 1
# TYPE platform_health_status gauge
platform_health_status{component="postgresql"} 1
"""
    summary = client.summarize(text)
    assert summary["http_requests_total"] == 12
    assert summary["cache_hit_rate"] == pytest.approx(0.8)
    assert summary["platform_health"]["postgresql"] == 1

from __future__ import annotations

from typing import Callable, Optional

from apps.web.streamlit_app.api_client.base import BaseApiClient
from apps.web.streamlit_app.api_client.models import LoginRequest, RefreshTokenRequest, TokenResponse
from apps.web.streamlit_app.config import WebSettings


class AuthApiClient(BaseApiClient):
    def login(self, username: str, password: str) -> TokenResponse:
        payload = LoginRequest(username=username, password=password)
        data = self._request("POST", "/v1/auth/login", json=payload.model_dump(), allow_refresh=False).json()
        return TokenResponse.model_validate(data)

    def refresh(self, refresh_token: str) -> TokenResponse:
        payload = RefreshTokenRequest(refresh_token=refresh_token)
        data = self._request("POST", "/v1/auth/refresh", json=payload.model_dump(), allow_refresh=False).json()
        return TokenResponse.model_validate(data)


def build_auth_client(settings: Optional[WebSettings] = None) -> AuthApiClient:
    return AuthApiClient(settings or WebSettings.from_env())


def build_authenticated_client(
    *,
    access_token: Optional[str] = None,
    api_key: Optional[str] = None,
    refresh_callback: Optional[Callable[[], str]] = None,
    settings: Optional[WebSettings] = None,
) -> BaseApiClient:
    return BaseApiClient(
        settings or WebSettings.from_env(),
        access_token=access_token,
        api_key=api_key,
        refresh_callback=refresh_callback,
    )

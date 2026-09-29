from __future__ import annotations

import asyncio

import pytest

from apps.api.app.core.auth.api_keys import ApiKeyAuthenticator
from apps.api.app.core.auth.identity import UserRole
from apps.api.app.core.auth.jwt_tokens import JwtTokenService
from apps.api.app.core.auth.service import AuthService
from apps.api.app.core.config import AuthSettings
from apps.api.app.core.errors import UnauthorizedError
from apps.api.app.core.auth.refresh_tokens import RefreshTokenService, RefreshTokenStore


def _build_auth_service() -> AuthService:
    settings = AuthSettings(
        enabled=True,
        users="analyst:secret:analyst",
        api_keys="test-key:analyst-1:analyst:analyst-user",
    )
    jwt_service = JwtTokenService(settings)
    refresh_service = RefreshTokenService(
        jwt_service=jwt_service,
        refresh_store=RefreshTokenStore(None, settings),
        settings=settings,
    )
    return AuthService(
        settings=settings,
        jwt_service=jwt_service,
        api_key_auth=ApiKeyAuthenticator(settings),
        refresh_service=refresh_service,
    )


def test_login_returns_token_pair() -> None:
    service = _build_auth_service()
    tokens = asyncio.run(service.login(username="analyst", password="secret"))
    assert tokens.access_token
    assert tokens.refresh_token
    assert tokens.expires_in > 0


def test_api_key_authentication_resolves_role() -> None:
    service = _build_auth_service()
    identity = service.authenticate_api_key("test-key")
    assert identity.user_id == "analyst-1"
    assert identity.role == UserRole.ANALYST


def test_invalid_password_raises_unauthorized() -> None:
    service = _build_auth_service()
    with pytest.raises(UnauthorizedError):
        asyncio.run(service.login(username="analyst", password="wrong"))


def test_refresh_rotates_tokens() -> None:
    service = _build_auth_service()
    initial = asyncio.run(service.login(username="analyst", password="secret"))
    refreshed = asyncio.run(service.refresh(refresh_token=initial.refresh_token))
    assert refreshed.access_token != initial.access_token
    assert refreshed.refresh_token != initial.refresh_token

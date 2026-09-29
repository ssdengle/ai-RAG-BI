from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Request
from redis.asyncio import Redis

from apps.api.app.core.auth.api_keys import ApiKeyAuthenticator
from apps.api.app.core.auth.jwt_tokens import JwtTokenService
from apps.api.app.core.auth.refresh_tokens import RefreshTokenService, RefreshTokenStore
from apps.api.app.core.auth.service import AuthService
from apps.api.app.core.cache import CacheClient
from apps.api.app.core.config import Settings


@dataclass
class PlatformServices:
    auth_service: AuthService
    cache_client: CacheClient
    jwt_service: JwtTokenService


def build_platform_services(settings: Settings, redis_client: Optional[Redis] = None) -> PlatformServices:
    jwt_service = JwtTokenService(settings.auth)
    refresh_store = RefreshTokenStore(redis_client, settings.auth)
    refresh_service = RefreshTokenService(
        jwt_service=jwt_service,
        refresh_store=refresh_store,
        settings=settings.auth,
    )
    auth_service = AuthService(
        settings=settings.auth,
        jwt_service=jwt_service,
        api_key_auth=ApiKeyAuthenticator(settings.auth),
        refresh_service=refresh_service,
    )
    cache_client = CacheClient(redis_client, settings.cache)
    return PlatformServices(
        auth_service=auth_service,
        cache_client=cache_client,
        jwt_service=jwt_service,
    )


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.platform.auth_service


def get_cache_client(request: Request) -> CacheClient:
    return request.app.state.platform.cache_client

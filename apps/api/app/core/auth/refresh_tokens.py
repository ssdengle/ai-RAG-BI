from __future__ import annotations

import json
from typing import Optional

from redis.asyncio import Redis

from apps.api.app.core.auth.jwt_tokens import JwtTokenService
from apps.api.app.core.config import AuthSettings
from apps.api.app.core.errors import UnauthorizedError


class RefreshTokenStore:
    """Persists refresh token JTIs in Redis to support rotation and revocation."""

    def __init__(self, redis_client: Optional[Redis], settings: AuthSettings) -> None:
        self._redis = redis_client
        self._settings = settings
        self._memory: dict[str, str] = {}

    async def store(self, *, jti: str, user_id: str) -> None:
        key = _refresh_key(jti)
        ttl_seconds = self._settings.refresh_token_expire_days * 86400
        if self._redis is not None:
            await self._redis.setex(key, ttl_seconds, user_id.encode("utf-8"))
            return
        self._memory[key] = user_id

    async def validate(self, *, jti: str, user_id: str) -> None:
        key = _refresh_key(jti)
        if self._redis is not None:
            stored = await self._redis.get(key)
            if stored is None or stored.decode("utf-8") != user_id:
                raise UnauthorizedError("Refresh token is invalid or revoked.", code="invalid_refresh_token")
            return
        if self._memory.get(key) != user_id:
            raise UnauthorizedError("Refresh token is invalid or revoked.", code="invalid_refresh_token")

    async def revoke(self, *, jti: str) -> None:
        key = _refresh_key(jti)
        if self._redis is not None:
            await self._redis.delete(key)
            return
        self._memory.pop(key, None)


class RefreshTokenService:
    def __init__(
        self,
        *,
        jwt_service: JwtTokenService,
        refresh_store: RefreshTokenStore,
        settings: AuthSettings,
    ) -> None:
        self._jwt_service = jwt_service
        self._refresh_store = refresh_store
        self._settings = settings

    async def issue_refresh_token(self, identity) -> str:
        token = self._jwt_service.create_refresh_token(identity)
        payload = self._jwt_service.decode_token(token, expected_type="refresh")
        await self._refresh_store.store(jti=str(payload["jti"]), user_id=str(payload["sub"]))
        return token

    async def rotate(self, refresh_token: str):
        payload = self._jwt_service.decode_token(refresh_token, expected_type="refresh")
        user_id = str(payload["sub"])
        jti = str(payload["jti"])
        await self._refresh_store.validate(jti=jti, user_id=user_id)
        await self._refresh_store.revoke(jti=jti)
        identity = self._jwt_service.identity_from_refresh_payload(payload)
        access_token = self._jwt_service.create_access_token(identity)
        new_refresh = await self.issue_refresh_token(identity)
        return identity, access_token, new_refresh


def _refresh_key(jti: str) -> str:
    return f"auth:refresh:{jti}"

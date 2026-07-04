from __future__ import annotations

from typing import Optional

from fastapi import Request
from redis.asyncio import ConnectionPool, Redis
from redis.exceptions import RedisError

from apps.api.app.core.config import RedisSettings
from apps.api.app.core.errors import InfrastructureError
from apps.api.app.core.logging import get_logger


class RedisManager:
    def __init__(self, settings: RedisSettings) -> None:
        self._settings = settings
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[Redis] = None
        self._logger = get_logger("api.redis")

    @property
    def client(self) -> Redis:
        if self._client is None:
            raise InfrastructureError(
                "Redis client has not been initialized.",
                code="redis_not_initialized",
            )
        return self._client

    async def initialize(self, *, check_connection: bool = True) -> None:
        if self._pool is None:
            self._pool = ConnectionPool.from_url(
                self._settings.url,
                max_connections=self._settings.max_connections,
                decode_responses=False,
            )
            self._client = Redis(connection_pool=self._pool)

        if check_connection:
            await self.ping()

        self._logger.info("redis.initialized")

    async def ping(self) -> None:
        try:
            await self.client.ping()
        except RedisError as exc:
            raise InfrastructureError(
                "Redis connectivity check failed.",
                details=str(exc),
                code="redis_unavailable",
            ) from exc

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._logger.info("redis.client_closed")

        if self._pool is not None:
            await self._pool.aclose()
            self._logger.info("redis.pool_closed")


def get_redis_manager(request: Request) -> RedisManager:
    return request.app.state.redis


def get_redis_client(request: Request) -> Redis:
    return get_redis_manager(request).client

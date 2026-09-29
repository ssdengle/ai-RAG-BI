from __future__ import annotations

import time
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from apps.api.app.core.config import SecuritySettings
from apps.api.app.core.logging import get_logger


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-backed sliding-window rate limiter with in-memory fallback."""

    def __init__(self, app: object, *, settings: SecuritySettings) -> None:
        super().__init__(app)
        self._settings = settings
        self._memory_buckets: dict[str, list[float]] = {}
        self._logger = get_logger("api.rate_limit")

    async def dispatch(self, request: Request, call_next: object) -> Response:
        if not self._settings.rate_limit_enabled:
            return await call_next(request)

        identity = getattr(request.state, "identity", None)
        client_key = identity.user_id if identity is not None else request.client.host if request.client else "anonymous"
        bucket_key = f"{client_key}:{request.url.path}"

        allowed = await _check_rate_limit(
            request,
            bucket_key=bucket_key,
            limit=self._settings.rate_limit_requests,
            window_seconds=self._settings.rate_limit_window_seconds,
            memory_buckets=self._memory_buckets,
        )
        if not allowed:
            self._logger.warning("rate_limit.exceeded", client_key=client_key, path=request.url.path)
            return JSONResponse(
                status_code=429,
                content={"code": "rate_limit_exceeded", "message": "Too many requests. Please retry later."},
                headers={"Retry-After": str(self._settings.rate_limit_window_seconds)},
            )

        return await call_next(request)


async def _check_rate_limit(
    request: Request,
    *,
    bucket_key: str,
    limit: int,
    window_seconds: int,
    memory_buckets: dict[str, list[float]],
) -> bool:
    now = time.time()
    redis_client = getattr(getattr(request.app.state, "redis", None), "client", None)
    redis_key = f"ratelimit:{bucket_key}"

    if redis_client is not None:
        try:
            count = await redis_client.incr(redis_key)
            if count == 1:
                await redis_client.expire(redis_key, window_seconds)
            return int(count) <= limit
        except Exception:
            pass

    bucket = memory_buckets.setdefault(bucket_key, [])
    bucket[:] = [timestamp for timestamp in bucket if now - timestamp < window_seconds]
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from redis.asyncio import Redis

from apps.api.app.core.config import CacheSettings


class CacheClient:
    """Redis-backed cache with in-memory fallback for tests and degraded mode."""

    def __init__(self, redis_client: Optional[Redis], settings: CacheSettings) -> None:
        self._redis = redis_client
        self._settings = settings
        self._memory: dict[str, tuple[bytes, float]] = {}

    @property
    def enabled(self) -> bool:
        return self._settings.enabled

    async def get_json(self, key: str) -> Any | None:
        if not self.enabled:
            return None
        raw = await self._get_raw(key)
        if raw is None:
            return None
        return json.loads(raw.decode("utf-8"))

    async def set_json(self, key: str, value: Any, *, ttl_seconds: int) -> None:
        if not self.enabled:
            return
        payload = json.dumps(value, default=_json_default).encode("utf-8")
        await self._set_raw(key, payload, ttl_seconds=ttl_seconds)

    async def _get_raw(self, key: str) -> bytes | None:
        if self._redis is not None:
            try:
                value = await self._redis.get(key)
                if value is not None:
                    return value
            except Exception:
                pass
        entry = self._memory.get(key)
        if entry is None:
            return None
        expires_at, payload = entry
        if expires_at < _now_ts():
            self._memory.pop(key, None)
            return None
        return payload

    async def _set_raw(self, key: str, payload: bytes, *, ttl_seconds: int) -> None:
        if self._redis is not None:
            try:
                await self._redis.setex(key, ttl_seconds, payload)
                return
            except Exception:
                pass
        self._memory[key] = (_now_ts() + ttl_seconds, payload)


def build_cache_key(namespace: str, payload: Any) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=_json_default)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"cache:{namespace}:{digest}"


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")


def _now_ts() -> float:
    return datetime.now().timestamp()

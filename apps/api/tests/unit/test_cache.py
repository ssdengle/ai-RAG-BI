from __future__ import annotations

import asyncio

from apps.api.app.core.cache import CacheClient, build_cache_key
from apps.api.app.core.config import CacheSettings


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def setex(self, key: str, ttl: int, value: bytes):
        self.store[key] = value


def test_cache_client_stores_and_reads_json() -> None:
    cache = CacheClient(_FakeRedis(), CacheSettings(enabled=True))
    key = build_cache_key("retrieval", {"query": "revenue"})

    async def run():
        await cache.set_json(key, {"answer": "Revenue increased."}, ttl_seconds=60)
        return await cache.get_json(key)

    result = asyncio.run(run())
    assert result == {"answer": "Revenue increased."}


def test_cache_disabled_returns_none() -> None:
    cache = CacheClient(_FakeRedis(), CacheSettings(enabled=False))

    async def run():
        await cache.set_json("key", {"value": 1}, ttl_seconds=60)
        return await cache.get_json("key")

    assert asyncio.run(run()) is None

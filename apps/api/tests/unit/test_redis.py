from __future__ import annotations

import asyncio
from typing import Any

from apps.api.app.core.redis import RedisManager


class _FakePool:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


class _FakeRedisClient:
    def __init__(self, connection_pool: _FakePool) -> None:
        self.connection_pool = connection_pool
        self.closed = False
        self.ping_called = False

    async def ping(self) -> bool:
        self.ping_called = True
        return True

    async def aclose(self) -> None:
        self.closed = True


def test_redis_manager_initializes_pool_and_client(test_settings, monkeypatch) -> None:
    fake_pool = _FakePool()
    captured: dict[str, Any] = {}

    def fake_from_url(url: str, **kwargs: Any) -> _FakePool:
        captured["url"] = url
        captured["kwargs"] = kwargs
        return fake_pool

    monkeypatch.setattr("apps.api.app.core.redis.ConnectionPool.from_url", fake_from_url)
    monkeypatch.setattr("apps.api.app.core.redis.Redis", _FakeRedisClient)
    manager = RedisManager(test_settings.redis)

    asyncio.run(manager.initialize(check_connection=False))

    assert captured["url"] == test_settings.redis.url
    assert manager.client.connection_pool is fake_pool


def test_redis_manager_ping_runs_during_startup(test_settings, monkeypatch) -> None:
    fake_pool = _FakePool()
    fake_client = _FakeRedisClient(fake_pool)

    monkeypatch.setattr("apps.api.app.core.redis.ConnectionPool.from_url", lambda *args, **kwargs: fake_pool)
    monkeypatch.setattr("apps.api.app.core.redis.Redis", lambda connection_pool: fake_client)
    manager = RedisManager(test_settings.redis)

    asyncio.run(manager.initialize(check_connection=True))

    assert fake_client.ping_called is True


def test_redis_manager_close_shuts_down_client_and_pool(test_settings, monkeypatch) -> None:
    fake_pool = _FakePool()
    fake_client = _FakeRedisClient(fake_pool)

    monkeypatch.setattr("apps.api.app.core.redis.ConnectionPool.from_url", lambda *args, **kwargs: fake_pool)
    monkeypatch.setattr("apps.api.app.core.redis.Redis", lambda connection_pool: fake_client)
    manager = RedisManager(test_settings.redis)
    asyncio.run(manager.initialize(check_connection=False))

    asyncio.run(manager.close())

    assert fake_client.closed is True
    assert fake_pool.closed is True

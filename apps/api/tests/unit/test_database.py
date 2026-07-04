from __future__ import annotations

import asyncio
from typing import Any

from apps.api.app.core.database import DatabaseManager
from apps.api.app.core.errors import InfrastructureError


class _FakeResult:
    pass


class _FakeConnection:
    def __init__(self) -> None:
        self.executed = False

    async def __aenter__(self) -> "_FakeConnection":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    async def execute(self, statement: Any) -> _FakeResult:
        self.executed = True
        return _FakeResult()


class _FakeEngine:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.disposed = False

    def connect(self) -> _FakeConnection:
        if self.should_fail:
            raise InfrastructureError("boom", details="connection failed", code="database_unavailable")
        return _FakeConnection()

    async def dispose(self) -> None:
        self.disposed = True


def test_database_manager_initializes_engine_without_connecting(test_settings, monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_create_async_engine(url: str, **kwargs: Any) -> _FakeEngine:
        captured["url"] = url
        captured["kwargs"] = kwargs
        return _FakeEngine()

    monkeypatch.setattr("apps.api.app.core.database.create_async_engine", fake_create_async_engine)
    manager = DatabaseManager(test_settings.database)

    asyncio.run(manager.initialize(check_connection=False))

    assert captured["url"] == test_settings.database.url
    assert manager.session_factory is not None


def test_database_manager_runs_connectivity_check(test_settings, monkeypatch) -> None:
    fake_engine = _FakeEngine()
    monkeypatch.setattr(
        "apps.api.app.core.database.create_async_engine",
        lambda *args, **kwargs: fake_engine,
    )
    manager = DatabaseManager(test_settings.database)

    asyncio.run(manager.initialize(check_connection=True))

    assert manager.engine is fake_engine


def test_database_manager_dispose_closes_engine(test_settings, monkeypatch) -> None:
    fake_engine = _FakeEngine()
    monkeypatch.setattr(
        "apps.api.app.core.database.create_async_engine",
        lambda *args, **kwargs: fake_engine,
    )
    manager = DatabaseManager(test_settings.database)
    asyncio.run(manager.initialize(check_connection=False))

    asyncio.run(manager.dispose())

    assert fake_engine.disposed is True

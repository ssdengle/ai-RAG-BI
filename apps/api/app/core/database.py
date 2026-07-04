from __future__ import annotations

from typing import AsyncIterator, Optional

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from apps.api.app.core.config import DatabaseSettings
from apps.api.app.core.errors import InfrastructureError
from apps.api.app.core.logging import get_logger


class DatabaseManager:
    def __init__(self, settings: DatabaseSettings) -> None:
        self._settings = settings
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        self._logger = get_logger("api.database")

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            raise InfrastructureError(
                "Database engine has not been initialized.",
                code="database_not_initialized",
            )
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        if self._session_factory is None:
            raise InfrastructureError(
                "Database session factory has not been initialized.",
                code="database_session_factory_not_initialized",
            )
        return self._session_factory

    async def initialize(self, *, check_connection: bool = True) -> None:
        if self._engine is None:
            self._engine = create_async_engine(
                self._settings.url,
                echo=self._settings.echo,
                pool_pre_ping=True,
                pool_size=self._settings.pool_size,
                max_overflow=self._settings.max_overflow,
                connect_args={"timeout": self._settings.connect_timeout_seconds},
            )
            self._session_factory = async_sessionmaker(
                bind=self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

        if check_connection:
            await self.check_connection()

        self._logger.info("database.initialized")

    async def check_connection(self) -> None:
        try:
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            raise InfrastructureError(
                "PostgreSQL connectivity check failed.",
                details=str(exc),
                code="database_unavailable",
            ) from exc

    async def dispose(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
            self._logger.info("database.disposed")

    async def get_session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            yield session


def get_database_manager(request: Request) -> DatabaseManager:
    return request.app.state.database


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    database = get_database_manager(request)
    async for session in database.get_session():
        yield session

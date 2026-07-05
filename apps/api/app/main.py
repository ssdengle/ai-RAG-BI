from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from fastapi import FastAPI

from apps.api.app.api.bi import router as bi_router
from apps.api.app.api.documents import router as documents_router
from apps.api.app.api.health import router as health_router
from apps.api.app.api.qa import router as qa_router
from apps.api.app.api.rag import router as rag_router
from apps.api.app.core.config import Settings, get_settings
from apps.api.app.core.database import DatabaseManager
from apps.api.app.core.errors import ConfigurationError, register_exception_handlers
from apps.api.app.core.logging import RequestContextLoggingMiddleware, bind_context, configure_logging, get_logger
from apps.api.app.core.redis import RedisManager


def create_app(
    settings: Optional[Settings] = None,
    *,
    database_manager: Optional[DatabaseManager] = None,
    redis_manager: Optional[RedisManager] = None,
    perform_startup_checks: bool = True,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.logging)
    logger = get_logger("api.bootstrap")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = resolved_settings
        app.state.database = database_manager or DatabaseManager(resolved_settings.database)
        app.state.redis = redis_manager or RedisManager(resolved_settings.redis)

        bind_context(
            request_id=None,
            workflow_id=None,
            document_id=None,
            duration_ms=None,
            status_code=None,
            environment=resolved_settings.app.environment,
            service=resolved_settings.logging.service_name,
        )
        logger.info("application.startup.begin")

        try:
            await app.state.database.initialize(check_connection=perform_startup_checks)
            await app.state.redis.initialize(check_connection=perform_startup_checks)
        except Exception as exc:
            raise ConfigurationError(
                "Application startup failed due to infrastructure configuration.",
                details=str(exc),
                code="startup_failed",
            ) from exc

        logger.info("application.startup.complete")

        try:
            yield
        finally:
            logger.info("application.shutdown.begin")
            await app.state.database.dispose()
            await app.state.redis.close()
            logger.info("application.shutdown.complete")

    app = FastAPI(
        title="AI Business Intelligence Platform API",
        version="0.1.0",
        description="Backend services for ingestion, retrieval, and AI workflows.",
        lifespan=lifespan,
    )
    app.add_middleware(RequestContextLoggingMiddleware)
    register_exception_handlers(app)
    app.include_router(documents_router)
    app.include_router(bi_router)
    app.include_router(health_router)
    app.include_router(qa_router)
    app.include_router(rag_router)

    return app


app = create_app()

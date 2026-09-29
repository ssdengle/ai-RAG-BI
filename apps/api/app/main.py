from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.app.api.auth import router as auth_router
from apps.api.app.api.bi import router as bi_router
from apps.api.app.api.documents import router as documents_router
from apps.api.app.api.evaluation import router as evaluation_router
from apps.api.app.api.health import router as health_router
from apps.api.app.api.qa import router as qa_router
from apps.api.app.api.rag import router as rag_router
from apps.api.app.api.workflows import router as workflows_router
from apps.api.app.core.auth.middleware import AuthenticationMiddleware, AuthorizationMiddleware
from apps.api.app.core.config import Settings, get_settings
from apps.api.app.core.database import DatabaseManager
from apps.api.app.core.errors import ConfigurationError, register_exception_handlers
from apps.api.app.core.logging import RequestContextLoggingMiddleware, bind_context, configure_logging, get_logger
from apps.api.app.core.metrics import MetricsMiddleware, metrics_endpoint
from apps.api.app.core.openapi import build_openapi_schema
from apps.api.app.core.platform import build_platform_services
from apps.api.app.core.redis import RedisManager
from apps.api.app.core.security.headers import SecurityHeadersMiddleware
from apps.api.app.core.security.rate_limit import RateLimitMiddleware
from apps.api.app.core.security.secrets import SecretsManager
from apps.api.app.core.security.validation import RequestValidationMiddleware
from apps.api.app.core.telemetry import (
    configure_telemetry,
    instrument_fastapi,
    instrument_httpx,
    instrument_redis,
    instrument_sqlalchemy,
)


def create_app(
    settings: Optional[Settings] = None,
    *,
    database_manager: Optional[DatabaseManager] = None,
    redis_manager: Optional[RedisManager] = None,
    perform_startup_checks: bool = True,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.logging)
    configure_telemetry(resolved_settings.telemetry)
    instrument_httpx(resolved_settings.telemetry)
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

        redis_client = None
        if perform_startup_checks and hasattr(app.state.redis, "client"):
            try:
                redis_client = app.state.redis.client
            except Exception:
                redis_client = None

        app.state.platform = build_platform_services(resolved_settings, redis_client)
        app.state.secrets = SecretsManager(
            jwt_secret=resolved_settings.auth.jwt_secret,
            llm_api_key=resolved_settings.llm.api_key,
            postgres_password=resolved_settings.database.password,
            redis_password=resolved_settings.redis.password,
        )

        if perform_startup_checks and redis_client is not None:
            instrument_redis(redis_client, resolved_settings.telemetry)
            if app.state.database.engine is not None:
                instrument_sqlalchemy(app.state.database.engine.sync_engine, resolved_settings.telemetry)

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
        description=(
            "Enterprise backend for document ingestion, grounded retrieval, business intelligence, "
            "multi-agent workflows, and AI evaluation."
        ),
        lifespan=lifespan,
    )
    app.openapi = lambda: build_openapi_schema(app)

    _register_middleware(app, resolved_settings)
    register_exception_handlers(app)
    instrument_fastapi(app, resolved_settings.telemetry)

    if resolved_settings.metrics.enabled:
        app.add_api_route(resolved_settings.metrics.path, metrics_endpoint, methods=["GET"], tags=["monitoring"])

    app.include_router(auth_router)
    app.include_router(documents_router)
    app.include_router(bi_router)
    app.include_router(workflows_router)
    app.include_router(evaluation_router)
    app.include_router(health_router)
    app.include_router(qa_router)
    app.include_router(rag_router)

    return app


def _register_middleware(app: FastAPI, settings: Settings) -> None:
    app.add_middleware(RequestContextLoggingMiddleware)
    if settings.metrics.enabled:
        app.add_middleware(MetricsMiddleware)
    if settings.auth.enabled:
        app.add_middleware(AuthorizationMiddleware, settings=settings)
        app.add_middleware(AuthenticationMiddleware, settings=settings)
    app.add_middleware(RateLimitMiddleware, settings=settings.security)
    app.add_middleware(RequestValidationMiddleware, settings=settings.security)
    app.add_middleware(SecurityHeadersMiddleware, settings=settings.security)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.security.cors_origins.split(",") if origin.strip()],
        allow_credentials=settings.security.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )


app = create_app()

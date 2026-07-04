from __future__ import annotations

import logging
import sys
import time
import uuid
from typing import Optional

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from apps.api.app.core.config import LoggingSettings


def configure_logging(settings: LoggingSettings) -> None:
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
    ]

    renderer = (
        structlog.processors.JSONRenderer()
        if settings.json_logs
        else structlog.dev.ConsoleRenderer(colors=False)
    )

    logging.basicConfig(
        level=getattr(logging, settings.level.upper(), logging.INFO),
        format="%(message)s",
        stream=sys.stdout,
        force=True,
    )

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.level.upper(), logging.INFO)
        ),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    bind_context(
        request_id=None,
        workflow_id=None,
        document_id=None,
        duration_ms=None,
        status_code=None,
        service=settings.service_name,
        environment=None,
    )


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


def bind_context(**values: object) -> None:
    structlog.contextvars.bind_contextvars(**values)


def clear_logging_context() -> None:
    structlog.contextvars.clear_contextvars()


class RequestContextLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object) -> None:
        super().__init__(app)
        self._logger = get_logger("api.request")

    async def dispatch(self, request: Request, call_next: object) -> Response:
        clear_logging_context()
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        workflow_id = request.headers.get("X-Workflow-ID")
        document_id = request.headers.get("X-Document-ID")

        bind_context(
            request_id=request_id,
            workflow_id=workflow_id,
            document_id=document_id,
            duration_ms=None,
            status_code=None,
        )
        request.state.request_id = request_id
        request.state.workflow_id = workflow_id
        request.state.document_id = document_id

        start = time.perf_counter()
        response: Optional[Response] = None

        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            status_code = response.status_code if response is not None else 500

            bind_context(duration_ms=duration_ms, status_code=status_code)
            self._logger.info(
                "request.completed",
                method=request.method,
                path=request.url.path,
                query=str(request.url.query),
            )

            if response is not None:
                response.headers["X-Request-ID"] = request_id

            clear_logging_context()

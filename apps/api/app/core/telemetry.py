from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Optional

from apps.api.app.core.config import TelemetrySettings
from apps.api.app.core.logging import get_logger

_logger = get_logger("api.telemetry")
_TRACER = None
_OTEL_AVAILABLE = False

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.trace import Status, StatusCode

    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised when dependency missing
    trace = None
    Status = None
    StatusCode = None


def configure_telemetry(settings: TelemetrySettings) -> None:
    global _TRACER
    if not settings.enabled or not _OTEL_AVAILABLE:
        _logger.info("telemetry.disabled")
        return

    resource = Resource.create(
        {
            "service.name": settings.service_name,
            "service.version": settings.service_version,
            "deployment.environment": settings.environment,
        }
    )
    provider = TracerProvider(resource=resource)
    if settings.console_exporter:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    _TRACER = trace.get_tracer(settings.service_name)
    _logger.info("telemetry.enabled", exporter="console" if settings.console_exporter else "none")


def instrument_fastapi(app: object, settings: TelemetrySettings) -> None:
    if not settings.enabled or not _OTEL_AVAILABLE:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    except Exception as exc:  # pragma: no cover
        _logger.warning("telemetry.fastapi_instrumentation_failed", error=str(exc))


def instrument_sqlalchemy(engine: object, settings: TelemetrySettings) -> None:
    if not settings.enabled or not _OTEL_AVAILABLE:
        return
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        SQLAlchemyInstrumentor().instrument(engine=engine)
    except Exception as exc:  # pragma: no cover
        _logger.warning("telemetry.sqlalchemy_instrumentation_failed", error=str(exc))


def instrument_redis(client: object, settings: TelemetrySettings) -> None:
    if not settings.enabled or not _OTEL_AVAILABLE:
        return
    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor

        RedisInstrumentor().instrument(client=client)
    except Exception as exc:  # pragma: no cover
        _logger.warning("telemetry.redis_instrumentation_failed", error=str(exc))


def instrument_httpx(settings: TelemetrySettings) -> None:
    if not settings.enabled or not _OTEL_AVAILABLE:
        return
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
    except Exception as exc:  # pragma: no cover
        _logger.warning("telemetry.httpx_instrumentation_failed", error=str(exc))


@contextmanager
def start_span(name: str, *, attributes: Optional[dict[str, Any]] = None) -> Iterator[None]:
    if _TRACER is None or not _OTEL_AVAILABLE:
        yield
        return

    with _TRACER.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        try:
            yield
        except Exception as exc:
            if Status is not None and StatusCode is not None:
                span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise

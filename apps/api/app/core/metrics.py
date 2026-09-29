from __future__ import annotations

import time
from typing import Optional

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
)
WORKFLOW_RUNS_TOTAL = Counter(
    "workflow_runs_total",
    "Total workflow runs",
    ["status"],
)
WORKFLOW_DURATION_SECONDS = Histogram(
    "workflow_duration_seconds",
    "Workflow execution duration in seconds",
)
EVALUATION_RUNS_TOTAL = Counter(
    "evaluation_runs_total",
    "Total evaluation runs",
    ["status"],
)
EVALUATION_DURATION_SECONDS = Histogram(
    "evaluation_duration_seconds",
    "Evaluation run duration in seconds",
)
HEALTH_STATUS = Gauge(
    "platform_health_status",
    "Platform health status (1=ok, 0=degraded)",
    ["component"],
)
CACHE_HITS_TOTAL = Counter(
    "cache_hits_total",
    "Cache hits by namespace",
    ["namespace"],
)
CACHE_MISSES_TOTAL = Counter(
    "cache_misses_total",
    "Cache misses by namespace",
    ["namespace"],
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Records request count and latency metrics for Prometheus."""

    async def dispatch(self, request: Request, call_next: object) -> Response:
        start = time.perf_counter()
        response: Optional[Response] = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration = time.perf_counter() - start
            status = str(response.status_code if response is not None else 500)
            path = request.url.path
            HTTP_REQUESTS_TOTAL.labels(method=request.method, path=path, status=status).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(method=request.method, path=path).observe(duration)


def metrics_endpoint() -> StarletteResponse:
    return StarletteResponse(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def record_workflow_metrics(*, status: str, duration_seconds: float) -> None:
    WORKFLOW_RUNS_TOTAL.labels(status=status).inc()
    WORKFLOW_DURATION_SECONDS.observe(duration_seconds)


def record_evaluation_metrics(*, status: str, duration_seconds: float) -> None:
    EVALUATION_RUNS_TOTAL.labels(status=status).inc()
    EVALUATION_DURATION_SECONDS.observe(duration_seconds)


def set_health_metric(*, component: str, healthy: bool) -> None:
    HEALTH_STATUS.labels(component=component).set(1 if healthy else 0)


def record_cache_hit(namespace: str) -> None:
    CACHE_HITS_TOTAL.labels(namespace=namespace).inc()


def record_cache_miss(namespace: str) -> None:
    CACHE_MISSES_TOTAL.labels(namespace=namespace).inc()

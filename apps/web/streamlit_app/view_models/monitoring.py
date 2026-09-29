from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.web.streamlit_app.api_client import PlatformApiClient
from apps.web.streamlit_app.api_client.exceptions import ApiError


@dataclass
class MonitoringViewModel:
    health_status: str = "unknown"
    database_status: str = "unknown"
    redis_status: str = "unknown"
    api_status: str = "unknown"
    environment: str = "unknown"
    service: str = "unknown"
    http_requests_total: float = 0.0
    workflow_runs_total: float = 0.0
    evaluation_runs_total: float = 0.0
    cache_hits_total: float = 0.0
    cache_misses_total: float = 0.0
    cache_hit_rate: float = 0.0
    platform_health: dict[str, float] = field(default_factory=dict)
    raw_metric_count: int = 0
    errors: list[str] = field(default_factory=list)


def build_monitoring_view_model(client: PlatformApiClient) -> MonitoringViewModel:
    vm = MonitoringViewModel()
    try:
        live = client.health.live()
        vm.api_status = live.status
        vm.environment = live.environment
        vm.service = live.service
    except ApiError as exc:
        vm.errors.append(f"Live health: {exc}")

    try:
        ready = client.health.ready()
        vm.health_status = ready.status
        vm.database_status = ready.checks.get("postgresql", {}).get("status", "unknown")
        vm.redis_status = ready.checks.get("redis", {}).get("status", "unknown")
    except ApiError as exc:
        vm.errors.append(f"Ready health: {exc}")

    try:
        summary = client.metrics.summarize()
        vm.http_requests_total = float(summary.get("http_requests_total", 0))
        vm.workflow_runs_total = float(summary.get("workflow_runs_total", 0))
        vm.evaluation_runs_total = float(summary.get("evaluation_runs_total", 0))
        vm.cache_hits_total = float(summary.get("cache_hits_total", 0))
        vm.cache_misses_total = float(summary.get("cache_misses_total", 0))
        vm.cache_hit_rate = float(summary.get("cache_hit_rate", 0))
        vm.platform_health = dict(summary.get("platform_health", {}))
        vm.raw_metric_count = int(summary.get("raw_metric_count", 0))
    except ApiError as exc:
        vm.errors.append(f"Metrics: {exc}")

    return vm

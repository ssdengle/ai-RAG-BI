from __future__ import annotations

from apps.api.app.core.metrics import (
    record_cache_hit,
    record_evaluation_metrics,
    record_workflow_metrics,
    set_health_metric,
)


def test_metrics_helpers_do_not_raise() -> None:
    record_cache_hit("retrieval")
    record_workflow_metrics(status="completed", duration_seconds=1.2)
    record_evaluation_metrics(status="completed", duration_seconds=0.8)
    set_health_metric(component="postgresql", healthy=True)

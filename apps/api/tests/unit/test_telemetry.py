from __future__ import annotations

from apps.api.app.core.telemetry import configure_telemetry, start_span
from apps.api.app.core.config import TelemetrySettings


def test_telemetry_span_context_manager_runs_without_otel() -> None:
    configure_telemetry(TelemetrySettings(enabled=False))
    with start_span("test.span", attributes={"key": "value"}):
        assert True

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from apps.web.streamlit_app.api_client.base import BaseApiClient


@dataclass
class ParsedMetric:
    name: str
    labels: dict[str, str] = field(default_factory=dict)
    value: float = 0.0
    metric_type: str = "unknown"


class MetricsApiClient:
    def __init__(self, client: BaseApiClient) -> None:
        self._client = client

    def fetch_prometheus_text(self) -> str:
        return self._client.get_text("/metrics")

    def parse_metrics(self, text: str) -> list[ParsedMetric]:
        metrics: list[ParsedMetric] = []
        metric_type = "unknown"
        for line in text.splitlines():
            if line.startswith("# TYPE"):
                parts = line.split()
                if len(parts) >= 4:
                    metric_type = parts[3]
                continue
            if not line or line.startswith("#"):
                continue
            match = re.match(r"^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{.*\})?\s+(.+)$", line)
            if not match:
                continue
            name, labels_raw, value_raw = match.groups()
            labels: dict[str, str] = {}
            if labels_raw:
                for label_match in re.finditer(r'(\w+)="([^"]*)"', labels_raw):
                    labels[label_match.group(1)] = label_match.group(2)
            try:
                value = float(value_raw)
            except ValueError:
                continue
            metrics.append(ParsedMetric(name=name, labels=labels, value=value, metric_type=metric_type))
        return metrics

    def summarize(self, text: str | None = None) -> dict[str, Any]:
        raw = text or self.fetch_prometheus_text()
        parsed = self.parse_metrics(raw)
        summary: dict[str, Any] = {
            "http_requests_total": 0.0,
            "workflow_runs_total": 0.0,
            "evaluation_runs_total": 0.0,
            "cache_hits_total": 0.0,
            "cache_misses_total": 0.0,
            "platform_health": {},
            "raw_metric_count": len(parsed),
        }
        for metric in parsed:
            if metric.name == "http_requests_total":
                summary["http_requests_total"] += metric.value
            elif metric.name == "workflow_runs_total":
                summary["workflow_runs_total"] += metric.value
            elif metric.name == "evaluation_runs_total":
                summary["evaluation_runs_total"] += metric.value
            elif metric.name == "cache_hits_total":
                summary["cache_hits_total"] += metric.value
            elif metric.name == "cache_misses_total":
                summary["cache_misses_total"] += metric.value
            elif metric.name == "platform_health_status":
                component = metric.labels.get("component", "unknown")
                summary["platform_health"][component] = metric.value
        hits = summary["cache_hits_total"]
        misses = summary["cache_misses_total"]
        summary["cache_hit_rate"] = hits / (hits + misses) if (hits + misses) else 0.0
        return summary

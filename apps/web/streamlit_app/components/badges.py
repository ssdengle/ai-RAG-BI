from __future__ import annotations

from apps.web.streamlit_app.components.ui import escape, html_block, icon


def status_badge(label: str, *, tone: str = "neutral") -> str:
    return f'<span class="badge badge-{tone}">{escape(label)}</span>'


def render_status_badge(label: str, *, tone: str = "neutral") -> None:
    html_block(status_badge(label, tone=tone))


def role_badge(role: str) -> str:
    tone_map = {
        "admin": "primary",
        "analyst": "info",
        "reviewer": "warning",
        "viewer": "neutral",
    }
    return status_badge(role.upper(), tone=tone_map.get(role.lower(), "neutral"))


def render_role_badge(role: str) -> None:
    html_block(role_badge(role))


def health_badge(status: str) -> str:
    normalized = status.lower()
    if normalized in {"ok", "healthy", "up", "connected"}:
        return status_badge(status, tone="success")
    if normalized in {"degraded", "warning"}:
        return status_badge(status, tone="warning")
    if normalized in {"down", "failed", "error", "unhealthy"}:
        return status_badge(status, tone="danger")
    return status_badge(status, tone="neutral")


def render_health_badge(status: str) -> None:
    html_block(health_badge(status))


def confidence_badge(value: float | None) -> str:
    if value is None:
        return status_badge("N/A", tone="neutral")
    if value >= 0.8:
        tone = "success"
    elif value >= 0.5:
        tone = "warning"
    else:
        tone = "danger"
    return status_badge(f"{value * 100:.0f}% confidence", tone=tone)


def render_confidence_badge(value: float | None) -> None:
    html_block(confidence_badge(value))


def latency_badge(ms: float | None) -> str:
    if ms is None:
        return status_badge("—", tone="neutral")
    if ms < 1000:
        tone = "success"
    elif ms < 5000:
        tone="warning"
    else:
        tone = "danger"
    return status_badge(f"{ms:.0f} ms", tone=tone)


def provider_badge(provider: str | None, model: str | None = None) -> str:
    label = provider or "unknown"
    if model:
        label = f"{label} · {model}"
    return status_badge(label, tone="info")


def chip(label: str) -> str:
    return f'<span class="chip">{escape(label)}</span>'


def render_chips(labels: list[str]) -> None:
    if not labels:
        return
    html_block("".join(chip(item) for item in labels))

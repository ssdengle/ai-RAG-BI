from __future__ import annotations

from datetime import datetime
from typing import Any, Optional


def format_datetime(value: datetime | str | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, str):
        return value
    return value.strftime("%Y-%m-%d %H:%M UTC")


def format_bytes(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.1f} MB"


def format_percent(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.{digits}f}%"


def format_score(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


def truncate_text(text: str, max_length: int = 120) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 1] + "…"


def status_badge(status: str) -> str:
    normalized = status.lower().replace("_", " ")
    return normalized.title()

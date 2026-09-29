from __future__ import annotations

import html
import re
from typing import Any

_PROMPT_INJECTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
        r"disregard\s+(the\s+)?(system|above)\s+(prompt|instructions)",
        r"you\s+are\s+now\s+",
        r"<\s*/?\s*script",
        r"```\s*system",
        r"jailbreak",
        r"developer\s+mode",
    )
]

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_text(value: str, *, max_length: int = 20_000) -> str:
    cleaned = _CONTROL_CHARS.sub("", value)
    cleaned = html.escape(cleaned, quote=False)
    return cleaned[:max_length]


def sanitize_mapping(payload: dict[str, Any], *, max_length: int = 20_000) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, str):
            sanitized[key] = sanitize_text(value, max_length=max_length)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_mapping(value, max_length=max_length)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_text(item, max_length=max_length) if isinstance(item, str) else item
                for item in value
            ]
        else:
            sanitized[key] = value
    return sanitized


def detect_prompt_injection(text: str) -> list[str]:
    matches: list[str] = []
    for pattern in _PROMPT_INJECTION_PATTERNS:
        if pattern.search(text):
            matches.append(pattern.pattern)
    return matches


def mitigate_prompt_injection(text: str) -> str:
    mitigated = text
    for pattern in _PROMPT_INJECTION_PATTERNS:
        mitigated = pattern.sub("[filtered]", mitigated)
    return sanitize_text(mitigated)

from __future__ import annotations

import base64
import json
from typing import Any, Optional


def decode_jwt_payload(token: str) -> dict[str, Any]:
    """Decode JWT payload without signature verification (UI role gating only)."""
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload + padding)
        return json.loads(decoded)
    except (ValueError, json.JSONDecodeError):
        return {}


def extract_user_claims(token: str) -> dict[str, Any]:
    payload = decode_jwt_payload(token)
    return {
        "user_id": payload.get("sub"),
        "username": payload.get("username"),
        "role": payload.get("role", "viewer"),
        "auth_method": payload.get("auth_method", "jwt"),
        "expires_at": payload.get("exp"),
    }

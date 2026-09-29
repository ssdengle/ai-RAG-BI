from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.web.streamlit_app.utils.jwt_utils import extract_user_claims


@dataclass
class CurrentUserViewModel:
    user_id: str | None
    username: str
    role: str
    auth_method: str
    expires_at: int | None = None


def build_current_user_view_model(auth_state: dict[str, Any]) -> CurrentUserViewModel:
    if auth_state.get("auth_mode") == "api_key":
        return CurrentUserViewModel(
            user_id=auth_state.get("user_id"),
            username=auth_state.get("username", "api-key-user"),
            role=auth_state.get("role", "viewer"),
            auth_method="api_key",
        )
    token = auth_state.get("access_token", "")
    claims = extract_user_claims(token) if token else {}
    return CurrentUserViewModel(
        user_id=claims.get("user_id") or auth_state.get("user_id"),
        username=claims.get("username") or auth_state.get("username", "unknown"),
        role=claims.get("role") or auth_state.get("role", "viewer"),
        auth_method=claims.get("auth_method", "jwt"),
        expires_at=claims.get("expires_at") or auth_state.get("expires_at"),
    )

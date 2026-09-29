from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class UserRole(str, Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


class AuthMethod(str, Enum):
    JWT = "jwt"
    API_KEY = "api_key"
    OAUTH = "oauth"


@dataclass(frozen=True)
class UserIdentity:
    """Authenticated principal attached to each request."""

    user_id: str
    username: str
    role: UserRole
    auth_method: AuthMethod
    scopes: tuple[str, ...] = ()
    tenant_id: Optional[str] = None

    def has_role(self, role: UserRole) -> bool:
        return self.role == role

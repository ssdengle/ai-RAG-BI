from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

import jwt

from apps.api.app.core.auth.identity import AuthMethod, UserIdentity, UserRole
from apps.api.app.core.config import AuthSettings
from apps.api.app.core.errors import UnauthorizedError


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 0


class JwtTokenService:
    def __init__(self, settings: AuthSettings) -> None:
        self._settings = settings

    def create_access_token(self, identity: UserIdentity) -> str:
        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=self._settings.access_token_expire_minutes)
        payload = {
            "sub": identity.user_id,
            "username": identity.username,
            "role": identity.role.value,
            "auth_method": identity.auth_method.value,
            "scopes": list(identity.scopes),
            "tenant_id": identity.tenant_id,
            "type": "access",
            "jti": str(uuid4()),
            "iat": int(now.timestamp()),
            "exp": int(expires.timestamp()),
        }
        return jwt.encode(payload, self._settings.jwt_secret.get_secret_value(), algorithm=self._settings.jwt_algorithm)

    def create_refresh_token(self, identity: UserIdentity) -> str:
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=self._settings.refresh_token_expire_days)
        payload = {
            "sub": identity.user_id,
            "username": identity.username,
            "role": identity.role.value,
            "jti": str(uuid4()),
            "type": "refresh",
            "iat": int(now.timestamp()),
            "exp": int(expires.timestamp()),
        }
        return jwt.encode(payload, self._settings.jwt_secret.get_secret_value(), algorithm=self._settings.jwt_algorithm)

    def create_token_pair(self, identity: UserIdentity) -> TokenPair:
        return TokenPair(
            access_token=self.create_access_token(identity),
            refresh_token=self.create_refresh_token(identity),
            expires_in=self._settings.access_token_expire_minutes * 60,
        )

    def decode_token(self, token: str, *, expected_type: str) -> dict[str, Any]:
        try:
            payload = jwt.decode(
                token,
                self._settings.jwt_secret.get_secret_value(),
                algorithms=[self._settings.jwt_algorithm],
            )
        except jwt.ExpiredSignatureError as exc:
            raise UnauthorizedError("Token has expired.", code="token_expired") from exc
        except jwt.InvalidTokenError as exc:
            raise UnauthorizedError("Invalid token.", code="invalid_token") from exc

        if payload.get("type") != expected_type:
            raise UnauthorizedError("Invalid token type.", code="invalid_token_type")
        return payload

    def identity_from_access_token(self, token: str) -> UserIdentity:
        payload = self.decode_token(token, expected_type="access")
        return UserIdentity(
            user_id=str(payload["sub"]),
            username=str(payload.get("username", "")),
            role=UserRole(str(payload.get("role", UserRole.VIEWER.value))),
            auth_method=AuthMethod(str(payload.get("auth_method", AuthMethod.JWT.value))),
            scopes=tuple(payload.get("scopes") or []),
            tenant_id=payload.get("tenant_id"),
        )

    def identity_from_refresh_payload(self, payload: dict[str, Any]) -> UserIdentity:
        return UserIdentity(
            user_id=str(payload["sub"]),
            username=str(payload.get("username", "")),
            role=UserRole(str(payload.get("role", UserRole.VIEWER.value))),
            auth_method=AuthMethod.JWT,
        )

from __future__ import annotations

from typing import Optional

from apps.api.app.core.auth.api_keys import ApiKeyAuthenticator
from apps.api.app.core.auth.identity import UserIdentity, UserRole
from apps.api.app.core.auth.identity import AuthMethod
from apps.api.app.core.auth.jwt_tokens import JwtTokenService, TokenPair
from apps.api.app.core.auth.refresh_tokens import RefreshTokenService
from apps.api.app.core.config import AuthSettings
from apps.api.app.core.errors import UnauthorizedError


class AuthService:
    def __init__(
        self,
        *,
        settings: AuthSettings,
        jwt_service: JwtTokenService,
        api_key_auth: ApiKeyAuthenticator,
        refresh_service: RefreshTokenService,
    ) -> None:
        self._settings = settings
        self._jwt_service = jwt_service
        self._api_key_auth = api_key_auth
        self._refresh_service = refresh_service
        self._users = _parse_users(settings.users)

    def authenticate_password(self, *, username: str, password: str) -> UserIdentity:
        record = self._users.get(username)
        if record is None or record["password"] != password:
            raise UnauthorizedError("Invalid username or password.", code="invalid_credentials")
        return UserIdentity(
            user_id=record["user_id"],
            username=username,
            role=UserRole(record["role"]),
            auth_method=AuthMethod.JWT,
        )

    async def login(self, *, username: str, password: str) -> TokenPair:
        identity = self.authenticate_password(username=username, password=password)
        access_token = self._jwt_service.create_access_token(identity)
        refresh_token = await self._refresh_service.issue_refresh_token(identity)
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self._settings.access_token_expire_minutes * 60,
        )

    async def refresh(self, *, refresh_token: str) -> TokenPair:
        identity, access_token, new_refresh = await self._refresh_service.rotate(refresh_token)
        return TokenPair(
            access_token=access_token,
            refresh_token=new_refresh,
            expires_in=self._settings.access_token_expire_minutes * 60,
        )

    def authenticate_bearer(self, token: str) -> UserIdentity:
        return self._jwt_service.identity_from_access_token(token)

    def authenticate_api_key(self, api_key: str) -> UserIdentity:
        return self._api_key_auth.authenticate(api_key)


def _parse_users(raw: str) -> dict[str, dict[str, str]]:
    users: dict[str, dict[str, str]] = {}
    if not raw.strip():
        return users
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(":")
        if len(parts) < 3:
            continue
        username, password, role = parts[0], parts[1], parts[2]
        user_id = parts[3] if len(parts) > 3 else username
        users[username] = {"password": password, "role": role.lower(), "user_id": user_id}
    return users

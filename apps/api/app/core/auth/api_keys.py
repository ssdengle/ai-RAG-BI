from __future__ import annotations

from dataclasses import dataclass

from apps.api.app.core.auth.identity import AuthMethod, UserIdentity, UserRole
from apps.api.app.core.config import AuthSettings
from apps.api.app.core.errors import UnauthorizedError


@dataclass(frozen=True)
class ApiKeyRecord:
    key: str
    user_id: str
    username: str
    role: UserRole


class ApiKeyAuthenticator:
    def __init__(self, settings: AuthSettings) -> None:
        self._records = _parse_api_keys(settings.api_keys)

    def authenticate(self, api_key: str) -> UserIdentity:
        record = self._records.get(api_key)
        if record is None:
            raise UnauthorizedError("Invalid API key.", code="invalid_api_key")
        return UserIdentity(
            user_id=record.user_id,
            username=record.username,
            role=record.role,
            auth_method=AuthMethod.API_KEY,
        )


def _parse_api_keys(raw: str) -> dict[str, ApiKeyRecord]:
    records: dict[str, ApiKeyRecord] = {}
    if not raw.strip():
        return records

    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(":")
        if len(parts) < 3:
            continue
        key, user_id, role_value = parts[0], parts[1], parts[2]
        username = parts[3] if len(parts) > 3 else user_id
        records[key] = ApiKeyRecord(
            key=key,
            user_id=user_id,
            username=username,
            role=UserRole(role_value.lower()),
        )
    return records

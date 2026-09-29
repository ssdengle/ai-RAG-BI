from __future__ import annotations

from pydantic import SecretStr


class SecretsManager:
    """Centralizes access to configured secrets without exposing values in logs."""

    def __init__(
        self,
        *,
        jwt_secret: SecretStr,
        llm_api_key: SecretStr | None = None,
        postgres_password: SecretStr | None = None,
        redis_password: SecretStr | None = None,
    ) -> None:
        self._jwt_secret = jwt_secret
        self._llm_api_key = llm_api_key
        self._postgres_password = postgres_password
        self._redis_password = redis_password

    def get_jwt_secret(self) -> str:
        return self._jwt_secret.get_secret_value()

    def get_llm_api_key(self) -> str | None:
        return self._llm_api_key.get_secret_value() if self._llm_api_key else None

    def get_postgres_password(self) -> str | None:
        return self._postgres_password.get_secret_value() if self._postgres_password else None

    def get_redis_password(self) -> str | None:
        return self._redis_password.get_secret_value() if self._redis_password else None

    def redacted_summary(self) -> dict[str, bool]:
        return {
            "jwt_secret_configured": bool(self.get_jwt_secret()),
            "llm_api_key_configured": self.get_llm_api_key() is not None,
            "postgres_password_configured": self.get_postgres_password() is not None,
            "redis_password_configured": self.get_redis_password() is not None,
        }

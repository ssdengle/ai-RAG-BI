from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional, Union

from fastapi import Request
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_ENV_FILE = Path(".env")


class _SectionSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=DEFAULT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )


class AppSettings(_SectionSettings):
    name: str = Field(default="ai-business-intelligence-platform", validation_alias="APP_NAME")
    environment: Literal["development", "test", "staging", "production"] = Field(
        default="development",
        validation_alias="APP_ENV",
    )
    host: str = Field(default="0.0.0.0", validation_alias="API_HOST")
    port: int = Field(default=8000, validation_alias="API_PORT")

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


class DatabaseSettings(_SectionSettings):
    host: str = Field(default="postgres", validation_alias="POSTGRES_HOST")
    port: int = Field(default=5432, validation_alias="POSTGRES_PORT")
    database: str = Field(default="ai_bi_platform", validation_alias="POSTGRES_DB")
    username: str = Field(default="ai_bi_user", validation_alias="POSTGRES_USER")
    password: SecretStr = Field(default=SecretStr("change-me"), validation_alias="POSTGRES_PASSWORD")
    echo: bool = Field(default=False, validation_alias="POSTGRES_ECHO")
    pool_size: int = Field(default=5, validation_alias="POSTGRES_POOL_SIZE")
    max_overflow: int = Field(default=10, validation_alias="POSTGRES_MAX_OVERFLOW")
    connect_timeout_seconds: int = Field(default=5, validation_alias="POSTGRES_CONNECT_TIMEOUT_SECONDS")

    @property
    def url(self) -> str:
        password = self.password.get_secret_value()
        return (
            f"postgresql+asyncpg://{self.username}:{password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


class RedisSettings(_SectionSettings):
    host: str = Field(default="redis", validation_alias="REDIS_HOST")
    port: int = Field(default=6379, validation_alias="REDIS_PORT")
    database: int = Field(default=0, validation_alias="REDIS_DB")
    password: Optional[SecretStr] = Field(default=None, validation_alias="REDIS_PASSWORD")
    max_connections: int = Field(default=20, validation_alias="REDIS_MAX_CONNECTIONS")

    @property
    def url(self) -> str:
        password = self.password.get_secret_value() if self.password else ""
        credentials = f":{password}@" if password else ""
        return f"redis://{credentials}{self.host}:{self.port}/{self.database}"


class LoggingSettings(_SectionSettings):
    level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    json_logs: bool = Field(default=False, validation_alias="LOG_JSON")
    service_name: str = Field(default="api", validation_alias="LOG_SERVICE_NAME")


class LLMSettings(_SectionSettings):
    provider: str = Field(default="openai", validation_alias="LLM_PROVIDER")
    model: str = Field(default="gpt-4o-mini", validation_alias="LLM_MODEL")
    api_key: Optional[SecretStr] = Field(default=None, validation_alias="LLM_API_KEY")
    base_url: Optional[str] = Field(default=None, validation_alias="LLM_BASE_URL")
    timeout_seconds: int = Field(default=30, validation_alias="LLM_TIMEOUT_SECONDS")
    embedding_model: str = Field(
        default="text-embedding-3-small",
        validation_alias="LLM_EMBEDDING_MODEL",
    )
    embedding_dimensions: int = Field(default=1536, validation_alias="LLM_EMBEDDING_DIMENSIONS")
    embedding_batch_size: int = Field(default=32, validation_alias="LLM_EMBEDDING_BATCH_SIZE")
    embedding_max_retries: int = Field(default=3, validation_alias="LLM_EMBEDDING_MAX_RETRIES")


class Settings(BaseModel):
    app: AppSettings
    database: DatabaseSettings
    redis: RedisSettings
    logging: LoggingSettings
    llm: LLMSettings


def load_settings(*, env_file: Union[str, Path, None] = DEFAULT_ENV_FILE) -> Settings:
    return Settings(
        app=AppSettings(_env_file=env_file),
        database=DatabaseSettings(_env_file=env_file),
        redis=RedisSettings(_env_file=env_file),
        logging=LoggingSettings(_env_file=env_file),
        llm=LLMSettings(_env_file=env_file),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()


def get_request_settings(request: Request) -> Settings:
    return request.app.state.settings

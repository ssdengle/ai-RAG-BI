from pathlib import Path

from apps.api.app.core.config import clear_settings_cache, get_settings, load_settings


def test_load_settings_reads_values_from_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "APP_NAME=foundation-test-app",
                "APP_ENV=production",
                "API_HOST=0.0.0.0",
                "API_PORT=9000",
                "POSTGRES_HOST=db.example.internal",
                "POSTGRES_PORT=5544",
                "POSTGRES_DB=foundation",
                "POSTGRES_USER=foundation_user",
                "POSTGRES_PASSWORD=foundation_password",
                "REDIS_HOST=cache.example.internal",
                "REDIS_PORT=6390",
                "REDIS_DB=2",
                "LOG_LEVEL=DEBUG",
                "LOG_JSON=true",
                "LOG_SERVICE_NAME=foundation-api",
                "LLM_PROVIDER=anthropic",
                "LLM_MODEL=claude-sonnet",
                "LLM_TIMEOUT_SECONDS=45",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(env_file=env_file)

    assert settings.app.name == "foundation-test-app"
    assert settings.app.environment == "production"
    assert settings.app.port == 9000
    assert settings.database.host == "db.example.internal"
    assert settings.database.url.startswith("postgresql+asyncpg://foundation_user:")
    assert settings.redis.host == "cache.example.internal"
    assert settings.logging.json_logs is True
    assert settings.llm.provider == "anthropic"
    assert settings.llm.embedding_model == "text-embedding-3-small"
    assert settings.llm.embedding_dimensions == 1536


def test_environment_variables_override_env_file(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("APP_NAME=file-value\nAPP_ENV=development\n", encoding="utf-8")
    monkeypatch.setenv("APP_NAME", "environment-override")

    settings = load_settings(env_file=env_file)

    assert settings.app.name == "environment-override"


def test_cached_settings_can_be_cleared(monkeypatch) -> None:
    clear_settings_cache()
    monkeypatch.setenv("APP_NAME", "cached-app")
    first = get_settings()

    clear_settings_cache()
    monkeypatch.setenv("APP_NAME", "updated-app")
    second = get_settings()

    assert first.app.name == "cached-app"
    assert second.app.name == "updated-app"
    clear_settings_cache()

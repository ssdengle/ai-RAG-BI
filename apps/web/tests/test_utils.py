from __future__ import annotations

from apps.web.streamlit_app.config import WebSettings


def test_web_settings_from_env_uses_defaults(monkeypatch) -> None:
    monkeypatch.delenv("API_BASE_URL", raising=False)
    settings = WebSettings.from_env()
    assert settings.api_base_url == "http://localhost:8000"
    assert settings.max_retries == 2

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class WebSettings:
    api_base_url: str
    request_timeout_seconds: float
    max_retries: int
    retry_backoff_seconds: float

    @classmethod
    def from_env(cls) -> WebSettings:
        return cls(
            api_base_url=os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/"),
            request_timeout_seconds=float(os.getenv("WEB_REQUEST_TIMEOUT_SECONDS", "30")),
            max_retries=int(os.getenv("WEB_MAX_RETRIES", "2")),
            retry_backoff_seconds=float(os.getenv("WEB_RETRY_BACKOFF_SECONDS", "0.5")),
        )

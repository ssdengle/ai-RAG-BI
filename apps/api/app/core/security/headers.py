from __future__ import annotations

from fastapi import Response
from starlette.middleware.base import BaseHTTPMiddleware

from apps.api.app.core.config import SecuritySettings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds standard enterprise security headers to every response."""

    def __init__(self, app: object, *, settings: SecuritySettings) -> None:
        super().__init__(app)
        self._settings = settings

    async def dispatch(self, request, call_next) -> Response:
        response: Response = await call_next(request)
        if not self._settings.security_headers_enabled:
            return response

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-XSS-Protection", "0")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
        )
        if self._settings.hsts_enabled:
            response.headers.setdefault(
                "Strict-Transport-Security",
                f"max-age={self._settings.hsts_max_age_seconds}; includeSubDomains",
            )
        return response

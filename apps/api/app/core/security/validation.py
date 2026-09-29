from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from apps.api.app.core.config import SecuritySettings


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Validates request size limits using headers without consuming the body stream."""

    def __init__(self, app: object, *, settings: SecuritySettings) -> None:
        super().__init__(app)
        self._settings = settings

    async def dispatch(self, request: Request, call_next: object):
        if request.method in {"POST", "PUT", "PATCH"}:
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    if int(content_length) > self._settings.max_request_body_bytes:
                        return JSONResponse(
                            status_code=413,
                            content={
                                "code": "payload_too_large",
                                "message": "Request body exceeds the configured size limit.",
                            },
                        )
                except ValueError:
                    return JSONResponse(
                        status_code=400,
                        content={"code": "invalid_content_length", "message": "Invalid Content-Length header."},
                    )

        return await call_next(request)

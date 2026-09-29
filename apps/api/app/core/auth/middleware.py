from __future__ import annotations

import re
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from apps.api.app.core.auth.identity import UserIdentity
from apps.api.app.core.auth.rbac import Permission, has_permission, resolve_required_permission
from apps.api.app.core.auth.service import AuthService
from apps.api.app.core.config import Settings
from apps.api.app.core.errors import ForbiddenError, UnauthorizedError
from apps.api.app.core.logging import bind_context, get_logger


_PUBLIC_PATHS = {
    "/docs",
    "/redoc",
    "/openapi.json",
}


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Validates JWT bearer tokens or API keys and attaches user identity to the request."""

    def __init__(self, app: object, *, settings: Settings) -> None:
        super().__init__(app)
        self._settings = settings
        self._logger = get_logger("api.auth")

    async def dispatch(self, request: Request, call_next: object) -> Response:
        if not self._settings.auth.enabled or request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        if _is_public_route(request.method, request.url.path):
            return await call_next(request)

        auth_service: AuthService = request.app.state.platform.auth_service
        try:
            identity = _authenticate_request(request, auth_service)
        except UnauthorizedError as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"code": exc.code, "message": exc.message, "details": exc.details},
            )

        request.state.identity = identity
        bind_context(user_id=identity.user_id, role=identity.role.value, auth_method=identity.auth_method.value)
        return await call_next(request)


class AuthorizationMiddleware(BaseHTTPMiddleware):
    """Enforces RBAC permissions for every protected route."""

    def __init__(self, app: object, *, settings: Settings) -> None:
        super().__init__(app)
        self._settings = settings
        self._logger = get_logger("api.authorization")

    async def dispatch(self, request: Request, call_next: object) -> Response:
        if not self._settings.auth.enabled or request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        if _is_public_route(request.method, request.url.path):
            return await call_next(request)

        identity: Optional[UserIdentity] = getattr(request.state, "identity", None)
        if identity is None:
            return JSONResponse(
                status_code=401,
                content={"code": "unauthorized", "message": "Authentication is required."},
            )

        permission = resolve_required_permission(request.method, request.url.path)
        if permission is not None and not has_permission(identity, permission):
            self._logger.warning(
                "authorization.denied",
                user_id=identity.user_id,
                role=identity.role.value,
                permission=permission.value,
                path=request.url.path,
            )
            exc = ForbiddenError(
                "You do not have permission to access this resource.",
                details={"permission": permission.value},
                code="forbidden",
            )
            return JSONResponse(
                status_code=exc.status_code,
                content={"code": exc.code, "message": exc.message, "details": exc.details},
            )

        return await call_next(request)


def _authenticate_request(request: Request, auth_service: AuthService) -> UserIdentity:
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return auth_service.authenticate_api_key(api_key)

    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        if token:
            return auth_service.authenticate_bearer(token)

    raise UnauthorizedError("Authentication credentials were not provided.", code="missing_credentials")


def _is_public_route(method: str, path: str) -> bool:
    public_patterns = [
        (r"^GET$", r"^/v1/health/live$"),
        (r"^GET$", r"^/v1/health/ready$"),
        (r"^POST$", r"^/v1/auth/login$"),
        (r"^POST$", r"^/v1/auth/refresh$"),
        (r"^GET$", r"^/metrics$"),
    ]
    for method_pattern, path_pattern in public_patterns:
        if re.match(method_pattern, method) and re.match(path_pattern, path):
            return True
    return False

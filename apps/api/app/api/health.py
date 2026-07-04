from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from apps.api.app.core.config import get_request_settings
from apps.api.app.core.errors import InfrastructureError


router = APIRouter(prefix="/v1/health", tags=["health"])


@router.get("/live")
def liveness(request: Request) -> dict[str, str]:
    settings = get_request_settings(request)
    return {
        "status": "ok",
        "service": settings.app.name,
        "environment": settings.app.environment,
    }


@router.get("/ready")
async def readiness(request: Request) -> JSONResponse:
    database = request.app.state.database
    redis = request.app.state.redis
    checks = {
        "postgresql": {"status": "ok", "details": None},
        "redis": {"status": "ok", "details": None},
    }
    overall_status = status.HTTP_200_OK

    try:
        await database.check_connection()
    except InfrastructureError as exc:
        checks["postgresql"] = {"status": "error", "details": exc.details or exc.message}
        overall_status = status.HTTP_503_SERVICE_UNAVAILABLE

    try:
        await redis.ping()
    except InfrastructureError as exc:
        checks["redis"] = {"status": "error", "details": exc.details or exc.message}
        overall_status = status.HTTP_503_SERVICE_UNAVAILABLE

    payload = {
        "status": "ok" if overall_status == status.HTTP_200_OK else "degraded",
        "checks": checks,
    }
    return JSONResponse(status_code=overall_status, content=payload)

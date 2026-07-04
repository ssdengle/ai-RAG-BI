from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from apps.api.app.core.logging import get_logger


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Any = None
    request_id: Optional[str] = None


class ApplicationError(Exception):
    default_code = "application_error"
    default_status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(
        self,
        message: str,
        *,
        details: Any = None,
        code: Optional[str] = None,
        status_code: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        self.code = code or self.default_code
        self.status_code = status_code or self.default_status_code


class ValidationError(ApplicationError):
    default_code = "validation_error"
    default_status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class DomainError(ApplicationError):
    default_code = "domain_error"
    default_status_code = status.HTTP_400_BAD_REQUEST


class InfrastructureError(ApplicationError):
    default_code = "infrastructure_error"
    default_status_code = status.HTTP_503_SERVICE_UNAVAILABLE


class ExternalServiceError(ApplicationError):
    default_code = "external_service_error"
    default_status_code = status.HTTP_502_BAD_GATEWAY


class ConfigurationError(ApplicationError):
    default_code = "configuration_error"
    default_status_code = status.HTTP_500_INTERNAL_SERVER_ERROR


def register_exception_handlers(app: FastAPI) -> None:
    logger = get_logger("api.errors")

    @app.exception_handler(ApplicationError)
    async def handle_application_error(request: Request, exc: ApplicationError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.warning(
            "application.error",
            error_code=exc.code,
            status_code=exc.status_code,
            message=exc.message,
            details=exc.details,
            request_id=request_id,
        )
        return _build_error_response(
            exc.status_code,
            ErrorResponse(
                code=exc.code,
                message=exc.message,
                details=exc.details,
                request_id=request_id,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.warning(
            "request.validation_error",
            request_id=request_id,
            details=exc.errors(),
        )
        return _build_error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            ErrorResponse(
                code="validation_error",
                message="Request validation failed.",
                details=exc.errors(),
                request_id=request_id,
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.exception(
            "application.unhandled_exception",
            request_id=request_id,
        )
        return _build_error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            ErrorResponse(
                code="internal_server_error",
                message="An unexpected error occurred.",
                details=str(exc),
                request_id=request_id,
            ),
        )


def _build_error_response(status_code: int, payload: ErrorResponse) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(),
    )

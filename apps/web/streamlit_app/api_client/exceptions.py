from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ApiError(Exception):
    message: str
    status_code: int | None = None
    code: str | None = None
    details: Any = None

    def __str__(self) -> str:
        if self.code:
            return f"{self.code}: {self.message}"
        return self.message


class AuthenticationError(ApiError):
    pass


class AuthorizationError(ApiError):
    pass


class NotFoundError(ApiError):
    pass


class ValidationError(ApiError):
    pass


class RateLimitError(ApiError):
    pass

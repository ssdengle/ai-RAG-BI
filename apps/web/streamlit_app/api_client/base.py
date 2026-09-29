from __future__ import annotations

import time
from typing import Any, Callable, Optional

import httpx

from apps.web.streamlit_app.api_client.exceptions import (
    ApiError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from apps.web.streamlit_app.config import WebSettings


class BaseApiClient:
    """HTTP client with JWT/API-key auth, retries, and typed error handling."""

    def __init__(
        self,
        settings: WebSettings,
        *,
        access_token: Optional[str] = None,
        api_key: Optional[str] = None,
        refresh_callback: Optional[Callable[[], str]] = None,
    ) -> None:
        self._settings = settings
        self._access_token = access_token
        self._api_key = api_key
        self._refresh_callback = refresh_callback

    @property
    def base_url(self) -> str:
        return self._settings.api_base_url

    def set_access_token(self, token: Optional[str]) -> None:
        self._access_token = token

    def set_api_key(self, api_key: Optional[str]) -> None:
        self._api_key = api_key

    def _build_headers(self, extra: Optional[dict[str, str]] = None) -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "application/json"}
        if extra:
            headers.update(extra)
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        elif self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    def _parse_error(self, response: httpx.Response) -> ApiError:
        try:
            payload = response.json()
            message = payload.get("message", response.text or "Request failed")
            code = payload.get("code")
            details = payload.get("details")
        except Exception:
            message = response.text or "Request failed"
            code = None
            details = None

        status = response.status_code
        if status == 401:
            return AuthenticationError(message, status_code=status, code=code, details=details)
        if status == 403:
            return AuthorizationError(message, status_code=status, code=code, details=details)
        if status == 404:
            return NotFoundError(message, status_code=status, code=code, details=details)
        if status == 422:
            return ValidationError(message, status_code=status, code=code, details=details)
        if status == 429:
            return RateLimitError(message, status_code=status, code=code, details=details)
        return ApiError(message, status_code=status, code=code, details=details)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: Optional[dict[str, Any]] = None,
        data: Any = None,
        files: Any = None,
        headers: Optional[dict[str, str]] = None,
        allow_refresh: bool = True,
    ) -> httpx.Response:
        url = f"{self.base_url}{path}"
        attempt = 0
        last_error: Optional[Exception] = None

        while attempt <= self._settings.max_retries:
            try:
                with httpx.Client(timeout=self._settings.request_timeout_seconds) as client:
                    response = client.request(
                        method,
                        url,
                        json=json,
                        params=params,
                        data=data,
                        files=files,
                        headers=self._build_headers(headers),
                    )

                    if response.status_code == 401 and allow_refresh and self._refresh_callback:
                        refreshed = self._refresh_callback()
                        if refreshed:
                            self._access_token = refreshed
                            response = client.request(
                                method,
                                url,
                                json=json,
                                params=params,
                                data=data,
                                files=files,
                                headers=self._build_headers(headers),
                            )

                    if response.status_code >= 400:
                        error = self._parse_error(response)
                        if response.status_code in {429, 502, 503, 504} and attempt < self._settings.max_retries:
                            last_error = error
                            attempt += 1
                            time.sleep(self._settings.retry_backoff_seconds * attempt)
                            continue
                        raise error

                    return response
            except httpx.TimeoutException as exc:
                last_error = ApiError("Request timed out.", status_code=504, code="timeout")
                if attempt >= self._settings.max_retries:
                    raise last_error from exc
                attempt += 1
                time.sleep(self._settings.retry_backoff_seconds * attempt)
            except httpx.HTTPError as exc:
                last_error = ApiError(str(exc), code="network_error")
                if attempt >= self._settings.max_retries:
                    raise last_error from exc
                attempt += 1
                time.sleep(self._settings.retry_backoff_seconds * attempt)

        if last_error:
            raise last_error
        raise ApiError("Request failed after retries.")

    def get_json(self, path: str, *, params: Optional[dict[str, Any]] = None) -> Any:
        return self._request("GET", path, params=params).json()

    def post_json(self, path: str, *, json: Any = None) -> Any:
        return self._request("POST", path, json=json).json()

    def delete(self, path: str) -> None:
        self._request("DELETE", path)

    def post_multipart(self, path: str, *, data: dict[str, Any], files: dict[str, Any]) -> Any:
        return self._request("POST", path, data=data, files=files).json()

    def get_text(self, path: str) -> str:
        return self._request("GET", path).text

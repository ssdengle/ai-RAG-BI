from __future__ import annotations

from typing import Callable, Optional

from apps.web.streamlit_app.api_client.auth import AuthApiClient, build_auth_client
from apps.web.streamlit_app.api_client.base import BaseApiClient
from apps.web.streamlit_app.api_client.bi import BusinessIntelligenceApiClient
from apps.web.streamlit_app.api_client.documents import DocumentsApiClient
from apps.web.streamlit_app.api_client.evaluation import EvaluationApiClient
from apps.web.streamlit_app.api_client.health import HealthApiClient
from apps.web.streamlit_app.api_client.metrics import MetricsApiClient
from apps.web.streamlit_app.api_client.qa import QuestionAnsweringApiClient
from apps.web.streamlit_app.api_client.retrieval import RetrievalApiClient
from apps.web.streamlit_app.api_client.workflows import WorkflowsApiClient
from apps.web.streamlit_app.config import WebSettings


class PlatformApiClient:
    """Facade over domain-specific API clients sharing auth and retry behavior."""

    def __init__(
        self,
        settings: Optional[WebSettings] = None,
        *,
        access_token: Optional[str] = None,
        api_key: Optional[str] = None,
        refresh_callback: Optional[Callable[[], str]] = None,
    ) -> None:
        self.settings = settings or WebSettings.from_env()
        self._http = BaseApiClient(
            self.settings,
            access_token=access_token,
            api_key=api_key,
            refresh_callback=refresh_callback,
        )
        self.auth = AuthApiClient(self.settings)
        self.documents = DocumentsApiClient(self._http)
        self.retrieval = RetrievalApiClient(self._http)
        self.qa = QuestionAnsweringApiClient(self._http)
        self.bi = BusinessIntelligenceApiClient(self._http)
        self.workflows = WorkflowsApiClient(self._http)
        self.evaluation = EvaluationApiClient(self._http)
        self.health = HealthApiClient(self._http)
        self.metrics = MetricsApiClient(self._http)

    def set_access_token(self, token: Optional[str]) -> None:
        self._http.set_access_token(token)

    def set_api_key(self, api_key: Optional[str]) -> None:
        self._http.set_api_key(api_key)


def create_platform_client(
    *,
    access_token: Optional[str] = None,
    api_key: Optional[str] = None,
    refresh_callback: Optional[Callable[[], str]] = None,
) -> PlatformApiClient:
    return PlatformApiClient(
        access_token=access_token,
        api_key=api_key,
        refresh_callback=refresh_callback,
    )


def create_auth_client() -> AuthApiClient:
    return build_auth_client()

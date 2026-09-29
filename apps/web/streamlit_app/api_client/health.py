from __future__ import annotations

from apps.web.streamlit_app.api_client.base import BaseApiClient
from apps.web.streamlit_app.api_client.models import HealthLiveResponse, HealthReadyResponse


class HealthApiClient:
    def __init__(self, client: BaseApiClient) -> None:
        self._client = client

    def live(self) -> HealthLiveResponse:
        data = self._client.get_json("/v1/health/live")
        return HealthLiveResponse.model_validate(data)

    def ready(self) -> HealthReadyResponse:
        data = self._client.get_json("/v1/health/ready")
        return HealthReadyResponse.model_validate(data)

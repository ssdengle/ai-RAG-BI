from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.web.streamlit_app.api_client import PlatformApiClient
from apps.web.streamlit_app.api_client.exceptions import ApiError


@dataclass
class DashboardViewModel:
    total_documents: int = 0
    indexed_documents: int = 0
    total_chunks: int = 0
    indexed_chunks: int = 0
    total_companies: int = 0
    workflow_count: int = 0
    evaluation_run_count: int = 0
    health_status: str = "unknown"
    database_status: str = "unknown"
    redis_status: str = "unknown"
    recent_activity: list[dict[str, Any]] = field(default_factory=list)
    quick_actions: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def build_dashboard_view_model(
    client: PlatformApiClient,
    *,
    recent_activity: list[dict[str, Any]],
    workflow_history: list[dict[str, Any]],
    evaluation_history: list[dict[str, Any]],
    role: str,
) -> DashboardViewModel:
    vm = DashboardViewModel(
        workflow_count=len(workflow_history),
        evaluation_run_count=len(evaluation_history),
        recent_activity=recent_activity[:8],
    )
    try:
        stats = client.documents.get_statistics()
        vm.total_documents = stats.total_documents
        vm.total_chunks = stats.total_chunks
        vm.indexed_chunks = stats.indexed_chunks
        vm.indexed_documents = stats.indexed_chunks
    except ApiError as exc:
        vm.errors.append(f"Documents: {exc}")

    try:
        vm.total_companies = len(client.bi.list_companies())
    except ApiError as exc:
        vm.errors.append(f"Companies: {exc}")

    try:
        ready = client.health.ready()
        vm.health_status = ready.status
        vm.database_status = ready.checks.get("postgresql", {}).get("status", "unknown")
        vm.redis_status = ready.checks.get("redis", {}).get("status", "unknown")
    except ApiError as exc:
        vm.errors.append(f"Health: {exc}")

    if role in {"admin", "analyst"}:
        vm.quick_actions = ["Upload Document", "Run Workflow", "Ask Question", "Create Evaluation Run"]
    elif role == "reviewer":
        vm.quick_actions = ["Review Workflow", "Review Evaluation Report", "Browse Knowledge Base"]
    else:
        vm.quick_actions = ["Browse Documents", "Search Knowledge Base", "View BI Insights"]

    return vm

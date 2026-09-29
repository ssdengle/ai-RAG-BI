from __future__ import annotations

import re
from enum import Enum

from apps.api.app.core.auth.identity import UserIdentity, UserRole


class Permission(str, Enum):
    HEALTH_READ = "health:read"
    DOCUMENTS_READ = "documents:read"
    DOCUMENTS_WRITE = "documents:write"
    RETRIEVAL_READ = "retrieval:read"
    QA_READ = "qa:read"
    BI_READ = "bi:read"
    BI_WRITE = "bi:write"
    WORKFLOWS_READ = "workflows:read"
    WORKFLOWS_RUN = "workflows:run"
    WORKFLOWS_MANAGE = "workflows:manage"
    EVALUATION_READ = "evaluation:read"
    EVALUATION_RUN = "evaluation:run"
    EVALUATION_MANAGE = "evaluation:manage"
    AUTH_MANAGE = "auth:manage"
    METRICS_READ = "metrics:read"
    ADMIN_ALL = "admin:all"


ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
    UserRole.ADMIN: set(Permission),
    UserRole.ANALYST: {
        Permission.HEALTH_READ,
        Permission.DOCUMENTS_READ,
        Permission.DOCUMENTS_WRITE,
        Permission.RETRIEVAL_READ,
        Permission.QA_READ,
        Permission.BI_READ,
        Permission.BI_WRITE,
        Permission.WORKFLOWS_READ,
        Permission.WORKFLOWS_RUN,
        Permission.EVALUATION_READ,
        Permission.EVALUATION_RUN,
        Permission.EVALUATION_MANAGE,
    },
    UserRole.REVIEWER: {
        Permission.HEALTH_READ,
        Permission.DOCUMENTS_READ,
        Permission.RETRIEVAL_READ,
        Permission.QA_READ,
        Permission.BI_READ,
        Permission.WORKFLOWS_READ,
        Permission.WORKFLOWS_MANAGE,
        Permission.EVALUATION_READ,
    },
    UserRole.VIEWER: {
        Permission.HEALTH_READ,
        Permission.DOCUMENTS_READ,
        Permission.RETRIEVAL_READ,
        Permission.QA_READ,
        Permission.BI_READ,
        Permission.WORKFLOWS_READ,
        Permission.EVALUATION_READ,
    },
}


_ROUTE_RULES: list[tuple[str, str, Permission]] = [
    ("GET", r"^/v1/health/live$", Permission.HEALTH_READ),
    ("GET", r"^/v1/health/ready$", Permission.HEALTH_READ),
    ("GET", r"^/metrics$", Permission.METRICS_READ),
    ("POST", r"^/v1/auth/login$", Permission.HEALTH_READ),
    ("POST", r"^/v1/auth/refresh$", Permission.HEALTH_READ),
    ("GET", r"^/v1/documents$", Permission.DOCUMENTS_READ),
    ("GET", r"^/v1/documents/stats$", Permission.DOCUMENTS_READ),
    ("GET", r"^/v1/documents/[^/]+$", Permission.DOCUMENTS_READ),
    ("GET", r"^/v1/documents/[^/]+/chunks$", Permission.DOCUMENTS_READ),
    ("GET", r"^/v1/documents/[^/]+/chunks/[^/]+$", Permission.DOCUMENTS_READ),
    ("GET", r"^/v1/documents/[^/]+/indexing-status$", Permission.DOCUMENTS_READ),
    ("GET", r"^/v1/documents/[^/]+/indexing-visibility$", Permission.DOCUMENTS_READ),
    ("POST", r"^/v1/documents$", Permission.DOCUMENTS_WRITE),
    ("DELETE", r"^/v1/documents/[^/]+$", Permission.DOCUMENTS_WRITE),
    ("POST", r"^/v1/documents/[^/]+/index$", Permission.DOCUMENTS_WRITE),
    ("POST", r"^/v1/documents/[^/]+/reindex$", Permission.DOCUMENTS_WRITE),
    ("POST", r"^/v1/retrieval/search$", Permission.RETRIEVAL_READ),
    ("POST", r"^/v1/retrieval/context-preview$", Permission.RETRIEVAL_READ),
    ("POST", r"^/v1/qa/ask$", Permission.QA_READ),
    ("POST", r"^/v1/qa/ask/document/[^/]+$", Permission.QA_READ),
    ("POST", r"^/v1/qa/ask/documents$", Permission.QA_READ),
    ("POST", r"^/v1/rag/ingestion/preview$", Permission.DOCUMENTS_READ),
    ("GET", r"^/v1/bi/companies$", Permission.BI_READ),
    ("GET", r"^/v1/bi/companies/[^/]+$", Permission.BI_READ),
    ("POST", r"^/v1/bi/companies$", Permission.BI_WRITE),
    ("POST", r"^/v1/bi/companies/[^/]+/competitors$", Permission.BI_WRITE),
    ("GET", r"^/v1/bi/companies/[^/]+/competitors$", Permission.BI_READ),
    ("POST", r"^/v1/bi/companies/compare$", Permission.BI_READ),
    ("POST", r"^/v1/bi/companies/[^/]+/risks/summarize$", Permission.BI_READ),
    ("POST", r"^/v1/bi/trends/summarize$", Permission.BI_READ),
    ("POST", r"^/v1/bi/briefs/executive$", Permission.BI_READ),
    ("POST", r"^/v1/bi/risks/compare$", Permission.BI_READ),
    ("POST", r"^/v1/workflows/run$", Permission.WORKFLOWS_RUN),
    ("GET", r"^/v1/workflows/[^/]+$", Permission.WORKFLOWS_READ),
    ("GET", r"^/v1/workflows/[^/]+/state$", Permission.WORKFLOWS_READ),
    ("GET", r"^/v1/workflows/[^/]+/trace$", Permission.WORKFLOWS_READ),
    ("POST", r"^/v1/workflows/[^/]+/retry$", Permission.WORKFLOWS_MANAGE),
    ("POST", r"^/v1/workflows/[^/]+/cancel$", Permission.WORKFLOWS_MANAGE),
    ("GET", r"^/v1/evaluation/datasets$", Permission.EVALUATION_READ),
    ("POST", r"^/v1/evaluation/datasets$", Permission.EVALUATION_MANAGE),
    ("GET", r"^/v1/evaluation/datasets/[^/]+/test-cases$", Permission.EVALUATION_READ),
    ("POST", r"^/v1/evaluation/datasets/[^/]+/test-cases$", Permission.EVALUATION_MANAGE),
    ("POST", r"^/v1/evaluation/datasets/[^/]+/runs$", Permission.EVALUATION_RUN),
    ("GET", r"^/v1/evaluation/runs/[^/]+$", Permission.EVALUATION_READ),
    ("GET", r"^/v1/evaluation/runs/[^/]+/results$", Permission.EVALUATION_READ),
    ("GET", r"^/v1/evaluation/runs/[^/]+/report$", Permission.EVALUATION_READ),
]

_COMPILED_RULES = [(method, re.compile(pattern), permission) for method, pattern, permission in _ROUTE_RULES]


def resolve_required_permission(method: str, path: str) -> Permission | None:
    for rule_method, pattern, permission in _COMPILED_RULES:
        if rule_method == method and pattern.match(path):
            return permission
    return Permission.ADMIN_ALL


def has_permission(identity: UserIdentity, permission: Permission) -> bool:
    if Permission.ADMIN_ALL in ROLE_PERMISSIONS.get(identity.role, set()):
        return True
    return permission in ROLE_PERMISSIONS.get(identity.role, set())

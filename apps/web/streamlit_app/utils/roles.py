from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


ROLE_LABELS = {
    UserRole.ADMIN: "Administrator",
    UserRole.ANALYST: "Analyst",
    UserRole.REVIEWER: "Reviewer",
    UserRole.VIEWER: "Viewer",
}


PERMISSIONS = {
    UserRole.ADMIN: {
        "documents.read",
        "documents.write",
        "retrieval.read",
        "qa.read",
        "bi.read",
        "bi.write",
        "workflows.read",
        "workflows.run",
        "workflows.manage",
        "evaluation.read",
        "evaluation.run",
        "evaluation.manage",
        "monitoring.read",
        "admin.read",
        "admin.write",
    },
    UserRole.ANALYST: {
        "documents.read",
        "documents.write",
        "retrieval.read",
        "qa.read",
        "bi.read",
        "bi.write",
        "workflows.read",
        "workflows.run",
        "evaluation.read",
        "evaluation.run",
        "evaluation.manage",
        "monitoring.read",
    },
    UserRole.REVIEWER: {
        "documents.read",
        "retrieval.read",
        "qa.read",
        "bi.read",
        "workflows.read",
        "workflows.manage",
        "evaluation.read",
        "monitoring.read",
    },
    UserRole.VIEWER: {
        "documents.read",
        "retrieval.read",
        "qa.read",
        "bi.read",
        "workflows.read",
        "evaluation.read",
        "monitoring.read",
    },
}


NAV_GROUPS = [
    {
        "label": "Overview",
        "items": [
            {"label": "Dashboard", "page": "pages/01_Dashboard.py", "permission": None},
            {"label": "Monitoring", "page": "pages/08_Monitoring.py", "permission": "monitoring.read"},
        ],
    },
    {
        "label": "Knowledge & Search",
        "items": [
            {"label": "Knowledge Base", "page": "pages/02_Knowledge_Base.py", "permission": "documents.read"},
            {"label": "Retrieval", "page": "pages/03_Retrieval.py", "permission": "retrieval.read"},
            {"label": "Question Answering", "page": "pages/04_Question_Answering.py", "permission": "qa.read"},
        ],
    },
    {
        "label": "Intelligence",
        "items": [
            {"label": "Business Intelligence", "page": "pages/05_Business_Intelligence.py", "permission": "bi.read"},
            {"label": "Workflow Center", "page": "pages/06_Workflow_Center.py", "permission": "workflows.read"},
            {"label": "Evaluation", "page": "pages/07_Evaluation.py", "permission": "evaluation.read"},
        ],
    },
    {
        "label": "Administration",
        "items": [
            {"label": "Administration", "page": "pages/09_Administration.py", "permission": "admin.read"},
        ],
    },
]

# Flat list preserved for tests and backward compatibility
NAV_ITEMS = [item for group in NAV_GROUPS for item in group["items"]]


def parse_role(role: str | None) -> UserRole:
    if role is None:
        return UserRole.VIEWER
    try:
        return UserRole(role.lower())
    except ValueError:
        return UserRole.VIEWER


def has_permission(role: UserRole, permission: str | None) -> bool:
    if permission is None:
        return True
    if role == UserRole.ADMIN:
        return True
    return permission in PERMISSIONS.get(role, set())


def visible_nav_items(role: UserRole) -> list[dict]:
    return [item for item in NAV_ITEMS if has_permission(role, item.get("permission"))]


def visible_nav_groups(role: UserRole) -> list[dict]:
    groups: list[dict] = []
    for group in NAV_GROUPS:
        items = [item for item in group["items"] if has_permission(role, item.get("permission"))]
        if items:
            groups.append({"label": group["label"], "items": items})
    return groups

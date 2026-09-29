from __future__ import annotations

from apps.web.streamlit_app.utils.roles import UserRole, has_permission, visible_nav_items


def test_viewer_can_read_documents_but_not_write() -> None:
    assert has_permission(UserRole.VIEWER, "documents.read")
    assert not has_permission(UserRole.VIEWER, "documents.write")


def test_analyst_can_run_workflows_but_not_manage() -> None:
    assert has_permission(UserRole.ANALYST, "workflows.run")
    assert not has_permission(UserRole.ANALYST, "workflows.manage")


def test_reviewer_sees_evaluation_but_not_administration() -> None:
    labels = [item["label"] for item in visible_nav_items(UserRole.REVIEWER)]
    assert "Evaluation" in labels
    assert "Administration" not in labels


def test_admin_sees_administration_page() -> None:
    labels = [item["label"] for item in visible_nav_items(UserRole.ADMIN)]
    assert "Administration" in labels

from __future__ import annotations

from apps.api.app.core.auth.identity import AuthMethod, UserIdentity, UserRole
from apps.api.app.core.auth.rbac import Permission, has_permission, resolve_required_permission


def test_admin_has_all_permissions() -> None:
    identity = UserIdentity(user_id="1", username="admin", role=UserRole.ADMIN, auth_method=AuthMethod.JWT)
    assert has_permission(identity, Permission.DOCUMENTS_WRITE)
    assert has_permission(identity, Permission.EVALUATION_MANAGE)


def test_viewer_cannot_write_documents() -> None:
    identity = UserIdentity(user_id="2", username="viewer", role=UserRole.VIEWER, auth_method=AuthMethod.JWT)
    assert has_permission(identity, Permission.DOCUMENTS_READ)
    assert not has_permission(identity, Permission.DOCUMENTS_WRITE)


def test_reviewer_can_manage_workflows() -> None:
    identity = UserIdentity(user_id="3", username="reviewer", role=UserRole.REVIEWER, auth_method=AuthMethod.JWT)
    assert has_permission(identity, Permission.WORKFLOWS_MANAGE)
    assert not has_permission(identity, Permission.EVALUATION_RUN)


def test_route_permission_resolution_for_qa_endpoint() -> None:
    permission = resolve_required_permission("POST", "/v1/qa/ask")
    assert permission == Permission.QA_READ


def test_route_permission_resolution_for_bi_summarize_endpoints() -> None:
    assert resolve_required_permission("POST", "/v1/bi/companies/company-1/risks/summarize") == Permission.BI_READ
    assert resolve_required_permission("POST", "/v1/bi/trends/summarize") == Permission.BI_READ
    assert resolve_required_permission("POST", "/v1/bi/briefs/executive") == Permission.BI_READ
    assert resolve_required_permission("GET", "/v1/bi/companies/company-1/competitors") == Permission.BI_READ


def test_route_permission_resolution_for_document_detail_endpoints() -> None:
    assert resolve_required_permission("GET", "/v1/documents/doc-1/chunks/chunk-1") == Permission.DOCUMENTS_READ
    assert resolve_required_permission("GET", "/v1/documents/doc-1/indexing-visibility") == Permission.DOCUMENTS_READ


def test_unmatched_route_falls_back_to_admin_all() -> None:
    assert resolve_required_permission("GET", "/v1/internal/admin-only") == Permission.ADMIN_ALL

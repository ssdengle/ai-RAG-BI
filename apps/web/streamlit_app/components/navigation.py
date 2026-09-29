from __future__ import annotations

import os

import streamlit as st

from apps.web.streamlit_app.components.badges import role_badge
from apps.web.streamlit_app.components.ui import escape, html_block, icon
from apps.web.streamlit_app.utils.roles import ROLE_LABELS, UserRole, visible_nav_groups
from apps.web.streamlit_app.utils.session import get_api_client, get_current_role, get_current_user, logout


APP_VERSION = "0.1.0"


def _fetch_health_status() -> str:
    try:
        ready = get_api_client().health.ready()
        return ready.status
    except Exception:
        return "unknown"


def render_sidebar_navigation(*, active_page: str | None = None) -> None:
    user = get_current_user()
    role = get_current_role()
    environment = os.getenv("APP_ENV", "development")
    health = _fetch_health_status()

    html_block(
        f"""
        <div class="sidebar-brand-block">
            <div class="sidebar-logo">
                <div class="sidebar-logo-mark">NX</div>
                <div>
                    <div class="sidebar-logo-text">Nexus AI</div>
                    <div class="sidebar-logo-sub">Enterprise Platform</div>
                </div>
            </div>
            <div class="sidebar-user">Signed in as <strong>{escape(user.get("username", "unknown"))}</strong></div>
            <div style="margin-top:0.5rem;display:flex;flex-wrap:wrap;gap:0.35rem;">
                {role_badge(role.value)}
                <span class="badge badge-neutral">{escape(environment)}</span>
                <span class="badge badge-neutral">v{escape(APP_VERSION)}</span>
            </div>
        </div>
        """
    )

    for group in visible_nav_groups(role):
        st.sidebar.markdown(f'<div class="sidebar-nav-group">{escape(group["label"])}</div>', unsafe_allow_html=True)
        for item in group["items"]:
            label = item["label"]
            if active_page and item["page"] == active_page:
                st.sidebar.markdown(f"**→ {label}**")
            else:
                st.sidebar.page_link(item["page"], label=label)

    dot_class = "ok" if health.lower() in {"ok", "healthy"} else "degraded"
    st.sidebar.markdown(
        f"""
        <div class="sidebar-status">
            <span class="status-dot {dot_class}"></span>
            System {escape(health)}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
    if st.sidebar.button(f"Sign out", use_container_width=True, type="primary"):
        logout()
        st.rerun()


def require_permission(permission: str) -> bool:
    from apps.web.streamlit_app.utils.roles import has_permission

    role = get_current_role()
    if has_permission(role, permission):
        return True
    st.warning("You do not have permission to access this section.")
    return False

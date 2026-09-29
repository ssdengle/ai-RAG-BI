"""Administration — roles, providers, environment, and diagnostics."""

from __future__ import annotations

import os

import streamlit as st

from apps.web.streamlit_app.components.badges import render_role_badge
from apps.web.streamlit_app.components.cards import empty_state, info_card
from apps.web.streamlit_app.components.layout import render_section_header
from apps.web.streamlit_app.components.notifications import handle_api_error, show_success
from apps.web.streamlit_app.components.page_shell import bootstrap_page
from apps.web.streamlit_app.components.tables import render_records_table
from apps.web.streamlit_app.components.ui import html_block
from apps.web.streamlit_app.utils.roles import PERMISSIONS, ROLE_LABELS, UserRole, has_permission
from apps.web.streamlit_app.utils.session import get_api_client, get_current_role, get_current_user, get_settings

bootstrap_page(
    "Administration",
    "Role management, provider configuration, environment settings, and read-only diagnostics.",
    active_page="pages/09_Administration.py",
    breadcrumb=[("Home", None), ("Administration", None)],
)

client = get_api_client()
role = get_current_role()
user = get_current_user()
settings = get_settings()
tabs = st.tabs(["Overview", "Roles", "Environment", "Diagnostics"])

with tabs[0]:
    render_section_header("Admin Console")
    username = user.get("username", "unknown")
    role_label = ROLE_LABELS.get(role, role.value)
    info_card(
        title="Signed in",
        body=f"{username} · {role_label}",
        icon_name="admin_panel_settings",
    )
    if not has_permission(role, "admin.read"):
        st.warning("Your role has limited admin visibility.")

with tabs[1]:
    render_section_header("Role Management")
    render_role_badge(role.value)
    st.markdown("**Permissions for current role**")
    perms = sorted(PERMISSIONS.get(role, set()))
    if perms:
        html_block(
            '<div style="display:flex;flex-wrap:wrap;gap:0.35rem;">'
            + "".join(f'<span class="chip chip-info">{p}</span>' for p in perms)
            + "</div>"
        )
    else:
        empty_state("No permissions", "Role permissions could not be loaded.", icon_name="shield")
    st.markdown("**All roles**")
    render_records_table(
        [
            {"role": ROLE_LABELS.get(r, r.value), "permissions": ", ".join(sorted(PERMISSIONS.get(r, set())))}
            for r in UserRole
        ]
    )

with tabs[2]:
    render_section_header("Environment")
    info_card(title="API base URL", body=settings.api_base_url, icon_name="link")
    info_card(title="Environment", body=os.getenv("APP_ENV", "development"), icon_name="public")
    info_card(title="Request timeout", body=f"{settings.request_timeout_seconds}s", icon_name="timer")
    info_card(title="Max retries", body=str(settings.max_retries), icon_name="replay")
    st.caption("Provider credentials are configured server-side via environment variables.")

with tabs[3]:
    render_section_header("Diagnostics")
    try:
        live = client.health.live()
        ready = client.health.ready()
        st.json(
            {
                "live": live.model_dump(mode="json"),
                "ready": ready.model_dump(mode="json"),
                "session": {
                    "username": user.get("username"),
                    "role": role.value,
                    "auth_mode": user.get("auth_mode"),
                },
            }
        )
    except Exception as exc:
        handle_api_error(exc)
    if has_permission(role, "admin.write"):
        if st.button("Clear session cache", type="secondary"):
            for key in list(st.session_state.keys()):
                if key.startswith("_cache_"):
                    del st.session_state[key]
            show_success("Session cache cleared.")

"""Dashboard — executive overview with metrics, health, and activity."""

from __future__ import annotations

import os

import streamlit as st

from apps.web.streamlit_app.components.badges import render_health_badge
from apps.web.streamlit_app.components.cards import activity_feed, render_action_cards, render_metric_card
from apps.web.streamlit_app.components.layout import render_hero_banner, render_section_header
from apps.web.streamlit_app.components.notifications import handle_api_error, loading
from apps.web.streamlit_app.components.page_shell import bootstrap_page
from apps.web.streamlit_app.utils.session import (
    SESSION_ACTIVITY,
    SESSION_EVALUATION_RUNS,
    SESSION_WORKFLOW_HISTORY,
    get_api_client,
    get_current_role,
    get_current_user,
)
from apps.web.streamlit_app.view_models.dashboard import build_dashboard_view_model

bootstrap_page(
    "Dashboard",
    "Operational overview across documents, intelligence workflows, and platform health.",
    active_page="pages/01_Dashboard.py",
    breadcrumb=[("Home", None), ("Dashboard", None)],
)

try:
    with loading("Loading platform overview..."):
        vm = build_dashboard_view_model(
            get_api_client(),
            recent_activity=st.session_state.get(SESSION_ACTIVITY, []),
            workflow_history=st.session_state.get(SESSION_WORKFLOW_HISTORY, []),
            evaluation_history=st.session_state.get(SESSION_EVALUATION_RUNS, []),
            role=get_current_user().get("role", "viewer"),
        )
except Exception as exc:
    handle_api_error(exc)
    st.stop()

render_hero_banner(
    title=f"Welcome back, {get_current_user().get('username', 'User')}",
    subtitle="Monitor knowledge assets, agent workflows, and evaluation performance from a unified control plane.",
    username=get_current_user().get("username", "User"),
    environment=os.getenv("APP_ENV", "development"),
    health_status=vm.health_status.title(),
)

render_section_header("Key Metrics")
row1 = st.columns(4)
render_metric_card(row1[0], label="Documents", value=vm.total_documents, icon_name="description", delta="Knowledge assets")
render_metric_card(row1[1], label="Indexed Chunks", value=vm.indexed_chunks, icon_name="dataset", delta="Vector-ready")
render_metric_card(row1[2], label="Companies", value=vm.total_companies, icon_name="corporate_fare")
render_metric_card(row1[3], label="Workflows", value=vm.workflow_count, icon_name="account_tree", delta="This session")

row2 = st.columns(4)
render_metric_card(row2[0], label="Total Chunks", value=vm.total_chunks, icon_name="grid_view")
render_metric_card(row2[1], label="Evaluation Runs", value=vm.evaluation_run_count, icon_name="monitoring")
render_metric_card(row2[2], label="Platform Health", value=vm.health_status.title(), icon_name="health_and_safety")
render_metric_card(row2[3], label="Your Role", value=get_current_role().value.title(), icon_name="badge")

render_section_header("Quick Actions")
render_action_cards(
    [
        (action, f"Navigate to {action}", "arrow_forward")
        for action in vm.quick_actions[:4]
    ]
    or [("Browse Knowledge Base", "Review indexed documents", "folder_open")]
)

render_section_header("System Health")
health_cols = st.columns(3)
with health_cols[0]:
    render_health_badge(vm.health_status)
    st.caption("API readiness")
with health_cols[1]:
    render_health_badge(vm.database_status)
    st.caption("PostgreSQL")
with health_cols[2]:
    render_health_badge(vm.redis_status)
    st.caption("Redis cache")

if vm.errors:
    for error in vm.errors:
        st.warning(error)

render_section_header("Recent Activity")
activity_feed(vm.recent_activity)

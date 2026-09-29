"""Monitoring — system health, metrics, and operational visibility."""

from __future__ import annotations

import streamlit as st

from apps.web.streamlit_app.components.badges import render_health_badge
from apps.web.streamlit_app.components.cards import empty_state, render_metric_card
from apps.web.streamlit_app.components.charts import bar_chart, gauge_chart
from apps.web.streamlit_app.components.layout import render_section_header
from apps.web.streamlit_app.components.notifications import handle_api_error, loading
from apps.web.streamlit_app.components.page_shell import bootstrap_page
from apps.web.streamlit_app.components.tables import render_records_table
from apps.web.streamlit_app.utils.session import get_api_client
from apps.web.streamlit_app.view_models.monitoring import build_monitoring_view_model

bootstrap_page(
    "Monitoring",
    "Prometheus metrics, service health, cache performance, and workflow observability.",
    active_page="pages/08_Monitoring.py",
    breadcrumb=[("Home", None), ("Monitoring", None)],
)

client = get_api_client()
tabs = st.tabs(["Health", "Metrics", "Cache", "Workflows"])

with tabs[0]:
    render_section_header("System Health")
    try:
        with loading("Checking system health..."):
            vm = build_monitoring_view_model(client)
        cols = st.columns(4)
        render_metric_card(cols[0], label="Overall", value=vm.health_status, icon_name="monitor_heart")
        render_metric_card(cols[1], label="Database", value=vm.database_status, icon_name="database")
        render_metric_card(cols[2], label="Redis", value=vm.redis_status, icon_name="memory")
        render_metric_card(cols[3], label="API", value=vm.api_status, icon_name="api")
        status_cols = st.columns(4)
        with status_cols[0]:
            render_health_badge(vm.health_status)
            st.caption("Platform")
        with status_cols[1]:
            render_health_badge(vm.database_status)
            st.caption("PostgreSQL")
        with status_cols[2]:
            render_health_badge(vm.redis_status)
            st.caption("Redis")
        with status_cols[3]:
            render_health_badge(vm.api_status)
            st.caption("REST API")
        if vm.errors:
            for error in vm.errors:
                st.warning(error)
    except Exception as exc:
        handle_api_error(exc)

with tabs[1]:
    render_section_header("Prometheus Metrics")
    try:
        with loading("Fetching metrics..."):
            vm = build_monitoring_view_model(client)
        if vm.raw_metric_count:
            render_records_table(
                [
                    {"metric": "HTTP requests", "value": vm.http_requests_total},
                    {"metric": "Workflow runs", "value": vm.workflow_runs_total},
                    {"metric": "Evaluation runs", "value": vm.evaluation_runs_total},
                    {"metric": "Raw metric count", "value": vm.raw_metric_count},
                ]
            )
            bar_chart(
                {
                    "HTTP": vm.http_requests_total,
                    "Workflows": vm.workflow_runs_total,
                    "Evaluations": vm.evaluation_runs_total,
                },
                "Operational counters",
            )
            if vm.platform_health:
                bar_chart(vm.platform_health, "Platform component health")
        else:
            empty_state("No metrics", "Metrics will appear when the API exposes Prometheus data.", icon_name="analytics")
    except Exception as exc:
        handle_api_error(exc)

with tabs[2]:
    render_section_header("Cache Performance")
    try:
        vm = build_monitoring_view_model(client)
        if vm.cache_hits_total or vm.cache_misses_total:
            cols = st.columns(3)
            render_metric_card(cols[0], label="Cache Hits", value=str(int(vm.cache_hits_total)), icon_name="bolt")
            render_metric_card(cols[1], label="Cache Misses", value=str(int(vm.cache_misses_total)), icon_name="block")
            render_metric_card(cols[2], label="Hit Rate", value=f"{vm.cache_hit_rate:.1%}", icon_name="speed")
            gauge_chart(vm.cache_hit_rate * 100, "Cache hit rate", max_value=100)
            bar_chart({"Hits": vm.cache_hits_total, "Misses": vm.cache_misses_total}, "Cache activity")
        else:
            empty_state("No cache data", "Cache statistics are not yet available.", icon_name="cached")
    except Exception as exc:
        handle_api_error(exc)

with tabs[3]:
    render_section_header("Workflow Metrics")
    try:
        vm = build_monitoring_view_model(client)
        if vm.workflow_runs_total:
            render_metric_card(st, label="Total Workflow Runs", value=str(int(vm.workflow_runs_total)), icon_name="account_tree")
            bar_chart({"Workflow runs": vm.workflow_runs_total}, "Workflow throughput")
        else:
            empty_state("No workflow metrics", "Execute workflows to populate metrics.", icon_name="account_tree")
    except Exception as exc:
        handle_api_error(exc)

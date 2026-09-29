"""Workflow Center — multi-agent workflow execution and inspection."""

from __future__ import annotations

import streamlit as st

from apps.web.streamlit_app.components.cards import empty_state, workflow_card
from apps.web.streamlit_app.components.charts import render_timeline
from apps.web.streamlit_app.components.layout import render_section_header
from apps.web.streamlit_app.components.notifications import handle_api_error, loading, show_success
from apps.web.streamlit_app.components.page_shell import bootstrap_page
from apps.web.streamlit_app.utils.roles import has_permission
from apps.web.streamlit_app.utils.session import (
    SESSION_WORKFLOW_HISTORY,
    get_api_client,
    get_current_role,
    record_activity,
    record_workflow,
)

bootstrap_page(
    "Workflow Center",
    "Execute, inspect, and manage LangGraph multi-agent workflows.",
    active_page="pages/06_Workflow_Center.py",
    breadcrumb=[("Home", None), ("Workflow Center", None)],
)

client = get_api_client()
role = get_current_role()
tab_run, tab_history, tab_inspect = st.tabs(["Execute", "History", "Inspect"])

with tab_run:
    if not has_permission(role, "workflows.run"):
        st.warning("Your role cannot execute workflows.")
    else:
        with st.form("run_workflow", border=False):
            user_request = st.text_area("User request", height=80)
            c1, c2 = st.columns(2)
            topic = c1.text_input("Topic")
            company_id = c2.text_input("Company ID")
            max_retries = st.slider("Max retries", 0, 5, 2)
            if st.form_submit_button("Run workflow", type="primary", use_container_width=True):
                try:
                    with loading("Executing workflow agents..."):
                        workflow = client.workflows.run_workflow(
                            user_request=user_request,
                            topic=topic,
                            company_id=company_id or None,
                            max_retries=max_retries,
                        )
                    record_workflow(workflow.workflow_id, workflow.topic, workflow.status)
                    record_activity("Workflow executed", workflow.workflow_id)
                    show_success(f"Workflow {workflow.workflow_id} · {workflow.status}")
                    st.json(workflow.model_dump(mode="json"))
                except Exception as exc:
                    handle_api_error(exc)

with tab_history:
    render_section_header("Session History")
    history = st.session_state.get(SESSION_WORKFLOW_HISTORY, [])
    if history:
        for item in history:
            workflow_card(workflow_id=item["workflow_id"], topic=item["topic"], status=item["status"])
    else:
        empty_state("No workflow history", "Workflows executed in this session appear here.", icon_name="history")

with tab_inspect:
    workflow_id = st.text_input("Workflow ID")
    c1, c2, c3 = st.columns(3)
    if c1.button("Load workflow") and workflow_id:
        try:
            workflow = client.workflows.get_workflow(workflow_id)
            st.json(workflow.model_dump(mode="json"))
            render_section_header("Agent Graph")
            st.markdown(" → ".join(workflow.plan) if workflow.plan else "No plan recorded")
            st.caption(f"Completed: {', '.join(workflow.completed_steps) or '—'}")
            if workflow.failed_steps:
                st.error(f"Failed steps: {', '.join(workflow.failed_steps)}")
        except Exception as exc:
            handle_api_error(exc)
    if c2.button("Load state") and workflow_id:
        try:
            state = client.workflows.get_state(workflow_id)
            st.json(state.model_dump(mode="json"))
        except Exception as exc:
            handle_api_error(exc)
    if c3.button("Load trace") and workflow_id:
        try:
            trace = client.workflows.get_trace(workflow_id)
            render_timeline([event.model_dump() for event in trace.trace])
        except Exception as exc:
            handle_api_error(exc)
    action_cols = st.columns(2)
    if has_permission(role, "workflows.manage") and action_cols[0].button("Retry workflow", type="primary") and workflow_id:
        try:
            workflow = client.workflows.retry_workflow(workflow_id)
            show_success(f"Retry started · {workflow.status}")
        except Exception as exc:
            handle_api_error(exc)
    if has_permission(role, "workflows.manage") and action_cols[1].button("Cancel workflow") and workflow_id:
        try:
            workflow = client.workflows.cancel_workflow(workflow_id)
            show_success(f"Workflow cancelled · {workflow.status}")
        except Exception as exc:
            handle_api_error(exc)

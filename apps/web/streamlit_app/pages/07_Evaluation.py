"""Evaluation — benchmark analytics and regression reporting."""

from __future__ import annotations

import streamlit as st

from apps.web.streamlit_app.components.cards import empty_state, render_metric_card
from apps.web.streamlit_app.components.charts import gauge_chart, radar_chart, render_failure_mode_chart, render_scorer_chart
from apps.web.streamlit_app.components.layout import render_section_header
from apps.web.streamlit_app.components.notifications import handle_api_error, loading, show_success
from apps.web.streamlit_app.components.page_shell import bootstrap_page
from apps.web.streamlit_app.components.tables import render_records_table
from apps.web.streamlit_app.utils.formatting import format_percent
from apps.web.streamlit_app.utils.roles import has_permission
from apps.web.streamlit_app.utils.session import (
    SESSION_EVALUATION_RUNS,
    get_api_client,
    get_current_role,
    record_activity,
    record_evaluation_run,
)

bootstrap_page(
    "Evaluation",
    "Benchmark datasets, evaluation runs, scorer analytics, and regression comparison.",
    active_page="pages/07_Evaluation.py",
    breadcrumb=[("Home", None), ("Evaluation", None)],
)

client = get_api_client()
role = get_current_role()
tabs = st.tabs(["Datasets", "Test Cases", "Runs", "Reports"])

with tabs[0]:
    render_section_header("Benchmark Datasets")
    try:
        datasets = client.evaluation.list_datasets()
        render_records_table([d.model_dump() for d in datasets])
        if has_permission(role, "evaluation.manage"):
            with st.expander("Create dataset"):
                with st.form("create_dataset"):
                    name = st.text_input("Dataset name")
                    description = st.text_area("Description")
                    target_type = st.selectbox("Target type", ["retrieval", "grounded_qa", "executive_brief", "workflow"])
                    if st.form_submit_button("Create dataset", type="primary"):
                        created = client.evaluation.create_dataset(name=name, description=description, target_type=target_type)
                        show_success(f"Created dataset {created.name}")
                        record_activity("Evaluation dataset created", created.dataset_id)
                        st.rerun()
    except Exception as exc:
        handle_api_error(exc)

with tabs[1]:
    dataset_id = st.text_input("Dataset ID", key="tc_dataset")
    if st.button("List test cases", type="primary") and dataset_id:
        try:
            cases = client.evaluation.list_test_cases(dataset_id)
            render_records_table([c.model_dump() for c in cases])
        except Exception as exc:
            handle_api_error(exc)
    if has_permission(role, "evaluation.manage"):
        with st.expander("Create test case"):
            with st.form("create_test_case"):
                tc_name = st.text_input("Test case name")
                query = st.text_area("Query")
                expected = st.text_area("Expected answer")
                if st.form_submit_button("Create test case") and dataset_id:
                    try:
                        client.evaluation.create_test_case(
                            dataset_id,
                            name=tc_name,
                            query=query,
                            expected_answer={"text": expected},
                        )
                        show_success("Test case created.")
                    except Exception as exc:
                        handle_api_error(exc)

with tabs[2]:
    run_dataset_id = st.text_input("Dataset ID", key="run_dataset")
    if has_permission(role, "evaluation.run") and st.button("Run evaluation", type="primary") and run_dataset_id:
        try:
            with loading("Running evaluation suite..."):
                run = client.evaluation.run_evaluation(run_dataset_id)
            record_evaluation_run(run.run_id, run_dataset_id, run.status)
            record_activity("Evaluation run completed", run.run_id)
            st.json(run.model_dump(mode="json"))
        except Exception as exc:
            handle_api_error(exc)
    render_section_header("Session Run History")
    history = st.session_state.get(SESSION_EVALUATION_RUNS, [])
    if history:
        render_records_table(history)
    else:
        empty_state("No evaluation runs", "Runs started in this session appear here.", icon_name="science")

with tabs[3]:
    run_id = st.text_input("Run ID")
    if st.button("Load report", type="primary") and run_id:
        try:
            report = client.evaluation.get_report(run_id)
            results = client.evaluation.get_results(run_id)
            cols = st.columns(4)
            render_metric_card(cols[0], label="Pass Rate", value=format_percent(report.pass_rate), icon_name="check_circle")
            render_metric_card(cols[1], label="Avg Score", value=f"{report.average_score:.2f}", icon_name="grade")
            render_metric_card(cols[2], label="Passed", value=f"{report.passed_test_cases}/{report.total_test_cases}", icon_name="task_alt")
            render_metric_card(cols[3], label="Status", value=report.status, icon_name="insights")
            gauge_chart(report.pass_rate * 100, "Pass rate gauge", max_value=100)
            if report.scorer_averages:
                radar_chart(list(report.scorer_averages.keys()), list(report.scorer_averages.values()), "Scorer radar")
            render_section_header("Failure Modes")
            render_failure_mode_chart(report.failure_mode_summary)
            render_section_header("Scorer Breakdown")
            render_scorer_chart(report.scorer_averages)
            render_section_header("Regression Comparison")
            st.json(report.regression_comparison)
            render_section_header("Results")
            render_records_table([r.model_dump() for r in results])
        except Exception as exc:
            handle_api_error(exc)

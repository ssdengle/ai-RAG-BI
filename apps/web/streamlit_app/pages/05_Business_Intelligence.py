"""Business Intelligence — executive insights and competitive analysis."""

from __future__ import annotations

import streamlit as st

from apps.web.streamlit_app.components.charts import bar_chart, heatmap
from apps.web.streamlit_app.components.citations import render_citation_accordion, render_citations
from apps.web.streamlit_app.components.layout import render_section_header
from apps.web.streamlit_app.components.notifications import handle_api_error, loading, show_success
from apps.web.streamlit_app.components.page_shell import bootstrap_page
from apps.web.streamlit_app.components.tables import render_records_table
from apps.web.streamlit_app.components.ui import html_block
from apps.web.streamlit_app.utils.formatting import format_percent
from apps.web.streamlit_app.utils.roles import has_permission
from apps.web.streamlit_app.utils.session import get_api_client, get_current_role, record_activity

bootstrap_page(
    "Business Intelligence",
    "Company intelligence, competitive analysis, risk and trend summaries, and executive briefs.",
    active_page="pages/05_Business_Intelligence.py",
    breadcrumb=[("Home", None), ("Business Intelligence", None)],
)

client = get_api_client()
role = get_current_role()
tabs = st.tabs(["Companies", "Competitors", "Comparison", "Risks", "Trends", "Executive Briefs"])

with tabs[0]:
    render_section_header("Company Profiles")
    try:
        if st.button("Refresh companies"):
            st.session_state.pop("bi_companies", None)
        companies = st.session_state.get("bi_companies")
        if companies is None:
            with loading("Loading companies..."):
                companies = client.bi.list_companies()
                st.session_state["bi_companies"] = companies
        for company in companies[:4]:
            html_block(
                f"""
                <div class="glass-card" style="margin-bottom:0.65rem;">
                    <div style="font-weight:600;color:var(--color-text);">{company.display_name}</div>
                    <div style="font-size:0.78rem;color:var(--color-text-muted);">{company.industry or '—'} · {company.company_id}</div>
                </div>
                """
            )
        render_records_table([c.model_dump() for c in companies])
        if has_permission(role, "bi.write"):
            with st.expander("Create company profile"):
                with st.form("create_company"):
                    name = st.text_input("Name")
                    display_name = st.text_input("Display Name")
                    industry = st.text_input("Industry")
                    if st.form_submit_button("Create", type="primary"):
                        created = client.bi.create_company(name=name, display_name=display_name, industry=industry or None)
                        show_success(f"Created {created.display_name}")
                        st.session_state.pop("bi_companies", None)
                        record_activity("Company created", created.company_id)
    except Exception as exc:
        handle_api_error(exc)

with tabs[1]:
    company_id = st.text_input("Company ID", key="competitor_company")
    if st.button("Load competitors", type="primary") and company_id:
        try:
            relationships = client.bi.list_competitors(company_id)
            render_records_table([r.model_dump() for r in relationships])
        except Exception as exc:
            handle_api_error(exc)

with tabs[2]:
    with st.form("compare_companies"):
        ids = st.text_input("Company IDs (comma-separated)")
        query = st.text_input("Comparison query", value="competitive positioning")
        if st.form_submit_button("Compare companies", type="primary"):
            try:
                result = client.bi.compare_companies(
                    company_ids=[item.strip() for item in ids.split(",") if item.strip()],
                    query=query,
                )
                render_records_table([c.model_dump() for c in result.companies])
                render_citations(result.citations)
            except Exception as exc:
                handle_api_error(exc)

with tabs[3]:
    risk_company = st.text_input("Company ID", key="risk_company")
    if st.button("Summarize risks", type="primary") and risk_company:
        try:
            summary = client.bi.summarize_risks(risk_company)
            heatmap(
                {cat.category: {cat.category: cat.average_score} for cat in summary.categories},
                "Risk intensity",
            )
            render_records_table([c.model_dump() for c in summary.categories])
            render_citation_accordion(summary.citations)
        except Exception as exc:
            handle_api_error(exc)

with tabs[4]:
    with st.form("trends"):
        trend_company = st.text_input("Company ID")
        document_type = st.text_input("Document Type")
        if st.form_submit_button("Summarize trends", type="primary"):
            try:
                summary = client.bi.summarize_trends(company_id=trend_company or None, document_type=document_type or None)
                bar_chart({t.topic: float(t.count) for t in summary.topics}, "Trend topics")
                render_records_table([t.model_dump() for t in summary.topics])
                render_citations(summary.citations)
            except Exception as exc:
                handle_api_error(exc)

with tabs[5]:
    with st.form("executive_brief"):
        topic = st.text_input("Topic")
        brief_company = st.text_input("Company ID")
        if st.form_submit_button("Generate executive brief", type="primary"):
            try:
                brief = client.bi.generate_executive_brief(topic=topic, company_id=brief_company or None)
                html_block(
                    f"""
                    <div class="glass-card">
                        <div style="font-size:1.1rem;font-weight:700;color:var(--color-text);margin-bottom:0.5rem;">{brief.title}</div>
                        <div style="color:var(--color-text-muted);line-height:1.6;">{brief.summary}</div>
                    </div>
                    """
                )
                st.metric("Confidence", format_percent(brief.confidence))
                for point in brief.key_points:
                    st.markdown(f"- {point}")
                render_citation_accordion(brief.citations)
                if brief.human_review_recommended:
                    st.warning("Human review recommended for this brief.")
            except Exception as exc:
                handle_api_error(exc)

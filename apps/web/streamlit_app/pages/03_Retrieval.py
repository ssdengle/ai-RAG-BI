"""Retrieval — hybrid search with context preview and citations."""

from __future__ import annotations

import streamlit as st

from apps.web.streamlit_app.components.cards import empty_state
from apps.web.streamlit_app.components.charts import bar_chart
from apps.web.streamlit_app.components.citations import render_citation_accordion, render_citations
from apps.web.streamlit_app.components.layout import render_section_header
from apps.web.streamlit_app.components.notifications import handle_api_error, loading
from apps.web.streamlit_app.components.page_shell import bootstrap_page
from apps.web.streamlit_app.components.tables import render_records_table
from apps.web.streamlit_app.utils.session import get_api_client, record_activity

bootstrap_page(
    "Retrieval",
    "Hybrid semantic and keyword search with citation-backed context assembly.",
    active_page="pages/03_Retrieval.py",
    breadcrumb=[("Home", None), ("Retrieval", None)],
)

client = get_api_client()
render_section_header("Search Console")

with st.form("retrieval_form", border=False):
    query = st.text_area("Query", placeholder="Search enterprise knowledge...", height=80)
    c1, c2, c3 = st.columns(3)
    mode = c1.selectbox("Retrieval mode", ["hybrid", "semantic", "keyword"])
    top_k = c2.slider("Top K results", 1, 20, 5)
    company = c3.text_input("Company filter")
    c4, c5 = st.columns(2)
    document_type = c4.text_input("Document type")
    tags = c5.text_input("Tags (comma-separated)")
    submitted = st.form_submit_button("Run retrieval", type="primary", use_container_width=True)

if submitted and query.strip():
    filters = {}
    if company:
        filters["company"] = company
    if document_type:
        filters["document_type"] = document_type
    if tags:
        filters["tags"] = [item.strip() for item in tags.split(",") if item.strip()]
    try:
        with loading("Retrieving context..."):
            search_result = client.retrieval.search(query=query, mode=mode, top_k=top_k, filters=filters or None)
            preview = client.retrieval.context_preview(query=query, mode=mode, top_k=top_k, filters=filters or None)
        record_activity("Retrieval search", query[:80])

        m1, m2, m3 = st.columns(3)
        m1.metric("Candidates", search_result.total_candidates)
        m2.metric("Chunks returned", len(search_result.chunks))
        m3.metric("Mode", search_result.mode)

        render_section_header("Similarity Scores")
        bar_chart({chunk.chunk_id[:8]: chunk.score for chunk in search_result.chunks}, "Top chunk scores")

        render_section_header("Retrieved Chunks")
        render_records_table(
            [
                {
                    "Chunk": item.chunk_id,
                    "Document": item.document_title or item.document_id,
                    "Score": round(item.score, 4),
                    "Preview": item.text[:140],
                }
                for item in search_result.chunks
            ]
        )

        render_section_header("Assembled Context")
        st.text_area("Context preview", preview.context, height=220, label_visibility="collapsed")
        st.caption(f"Chunks: {preview.chunk_count} · Truncated: {preview.truncated}")

        render_section_header("Citations")
        render_citations(search_result.citations)
        render_citation_accordion(search_result.citations)
    except Exception as exc:
        handle_api_error(exc)
else:
    empty_state("Ready to search", "Enter a query and configure filters to retrieve grounded context.", icon_name="search")

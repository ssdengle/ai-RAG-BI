"""Grounded Question Answering — chat-style Q&A interface."""

from __future__ import annotations

import streamlit as st

from apps.web.streamlit_app.components.badges import render_confidence_badge, render_provider_badge
from apps.web.streamlit_app.components.cards import empty_state
from apps.web.streamlit_app.components.citations import render_citation_accordion
from apps.web.streamlit_app.components.layout import render_section_header
from apps.web.streamlit_app.components.notifications import handle_api_error, loading
from apps.web.streamlit_app.components.page_shell import bootstrap_page
from apps.web.streamlit_app.components.ui import html_block
from apps.web.streamlit_app.utils.formatting import format_percent
from apps.web.streamlit_app.utils.session import get_api_client, record_activity

bootstrap_page(
    "Question Answering",
    "Ask grounded questions with confidence scoring and citation-backed answers.",
    active_page="pages/04_Question_Answering.py",
    breadcrumb=[("Home", None), ("Question Answering", None)],
)

client = get_api_client()

if "qa_messages" not in st.session_state:
    st.session_state.qa_messages = []

render_section_header("Conversation")
for message in st.session_state.qa_messages:
    css_class = "chat-bubble-user" if message["role"] == "user" else "chat-bubble-assistant"
    html_block(f'<div class="{css_class}">{message["content"]}</div>')

if not st.session_state.qa_messages:
    empty_state("Start a conversation", "Ask a question about your enterprise knowledge base.", icon_name="forum")

scope = st.radio("Scope", ["All documents", "Single document", "Selected documents"], horizontal=True)
with st.form("qa_form", border=False):
    question = st.text_area("Your question", height=90)
    c1, c2 = st.columns(2)
    mode = c1.selectbox("Retrieval mode", ["hybrid", "semantic", "keyword"])
    top_k = c2.slider("Top K", 1, 20, 5)
    document_id = st.text_input("Document ID (single scope)")
    document_ids = st.text_input("Document IDs (comma-separated)")
    submitted = st.form_submit_button("Ask", type="primary", use_container_width=True)

if submitted and question.strip():
    st.session_state.qa_messages.append({"role": "user", "content": question})
    try:
        with loading("Generating grounded answer..."):
            if scope == "Single document" and document_id:
                result = client.qa.ask_document(document_id, query=question, mode=mode, top_k=top_k)
            elif scope == "Selected documents" and document_ids:
                ids = [item.strip() for item in document_ids.split(",") if item.strip()]
                result = client.qa.ask_documents(ids, query=question, mode=mode, top_k=top_k)
            else:
                result = client.qa.ask(query=question, mode=mode, top_k=top_k)
        record_activity("Question answered", question[:80])
        st.session_state.qa_messages.append({"role": "assistant", "content": result.answer})

        render_section_header("Latest Answer")
        html_block(f'<div class="glass-card">{result.answer}</div>')

        badge_cols = st.columns(3)
        with badge_cols[0]:
            render_confidence_badge(result.confidence)
        with badge_cols[1]:
            render_provider_badge(result.llm_provider, result.llm_model)
        with badge_cols[2]:
            st.caption(f"Finish reason: {result.finish_reason or '—'}")

        with st.expander("Retrieved context", expanded=False):
            if result.context_preview:
                st.text_area("Context", result.context_preview, height=180, label_visibility="collapsed")

        with st.expander("Retrieval metadata", expanded=False):
            st.json(
                {
                    "mode": result.retrieval.mode,
                    "query": result.retrieval.query,
                    "total_candidates": result.retrieval.total_candidates,
                    "confidence": format_percent(result.confidence),
                }
            )

        render_citation_accordion(result.citations)
        st.rerun()
    except Exception as exc:
        handle_api_error(exc)

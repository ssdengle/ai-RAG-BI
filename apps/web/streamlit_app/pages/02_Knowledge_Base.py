"""Knowledge Base — document management and chunk exploration."""

from __future__ import annotations

import streamlit as st

from apps.web.streamlit_app.components.badges import render_chips, render_status_badge
from apps.web.streamlit_app.components.cards import document_card, empty_state
from apps.web.streamlit_app.components.layout import render_section_header
from apps.web.streamlit_app.components.notifications import handle_api_error, loading, show_success
from apps.web.streamlit_app.components.page_shell import bootstrap_page
from apps.web.streamlit_app.components.tables import render_records_table
from apps.web.streamlit_app.utils.roles import has_permission
from apps.web.streamlit_app.utils.session import get_api_client, get_current_role, record_activity
from apps.web.streamlit_app.view_models.documents import build_document_browse_view_model

bootstrap_page(
    "Knowledge Base",
    "Upload, browse, inspect chunks, and monitor indexing pipelines.",
    active_page="pages/02_Knowledge_Base.py",
    breadcrumb=[("Home", None), ("Knowledge Base", None)],
)

role = get_current_role()
client = get_api_client()
tab_browse, tab_upload, tab_detail = st.tabs(["Browse", "Upload", "Document Inspector"])

with tab_browse:
    render_section_header("Document Explorer")
    with st.form("doc_filters", border=False):
        c1, c2, c3, c4 = st.columns(4)
        search = c1.text_input("Search", placeholder="Filter by title or filename")
        company = c2.text_input("Company")
        document_type = c3.text_input("Document type")
        indexing_status = c4.selectbox("Indexing status", ["", "pending", "indexed", "failed", "indexing"])
        page = st.number_input("Page", min_value=1, value=1)
        submitted = st.form_submit_button("Apply filters", type="primary")
    if submitted or "kb_loaded" not in st.session_state:
        try:
            with loading("Loading documents..."):
                page_data = client.documents.list_documents(
                    search=search or None,
                    company=company or None,
                    document_type=document_type or None,
                    indexing_status=indexing_status or None,
                    page=int(page),
                    page_size=10,
                )
                vm = build_document_browse_view_model(page_data)
                st.session_state["kb_loaded"] = True
                st.session_state["kb_documents"] = vm.documents
                st.session_state["kb_total"] = vm.total
        except Exception as exc:
            handle_api_error(exc)
    documents = st.session_state.get("kb_documents", [])
    if documents:
        for doc in documents[:6]:
            document_card(
                filename=doc.get("filename", "Unknown"),
                document_id=doc.get("document_id", ""),
                company=doc.get("company"),
                status=doc.get("indexing_status", "unknown"),
                chunk_count=doc.get("chunk_count", 0),
            )
        with st.expander("Full table view", expanded=False):
            render_records_table(documents)
    else:
        empty_state("No documents found", "Upload a document or adjust your filters.", icon_name="folder_off")

with tab_upload:
    if not has_permission(role, "documents.write"):
        st.warning("Your role has read-only access to the knowledge base.")
    else:
        uploaded = st.file_uploader("Select document", type=["txt", "pdf", "docx", "md"])
        meta1, meta2 = st.columns(2)
        company = meta1.text_input("Company metadata")
        document_type = meta2.text_input("Document type metadata")
        if uploaded and st.button("Upload to knowledge base", type="primary"):
            try:
                with loading("Uploading document..."):
                    detail = client.documents.upload_document(
                        filename=uploaded.name,
                        content=uploaded.getvalue(),
                        content_type=uploaded.type or "application/octet-stream",
                        metadata={"company": company, "document_type": document_type},
                        chunking={"strategy": "semantic", "max_chunk_size": "800"},
                    )
                show_success(f"Uploaded {detail.filename}")
                record_activity("Document uploaded", detail.document_id)
            except Exception as exc:
                handle_api_error(exc)

with tab_detail:
    render_section_header("Document Inspector")
    document_id = st.text_input("Document ID", placeholder="Paste document UUID")
    chunk_id = st.text_input("Chunk ID (optional)")
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("Load detail") and document_id:
        try:
            detail = client.documents.get_document(document_id)
            st.json(detail.model_dump(mode="json"))
            render_chips(detail.tags)
        except Exception as exc:
            handle_api_error(exc)
    if c2.button("Indexing status") and document_id:
        try:
            status = client.documents.get_indexing_status(document_id)
            render_status_badge(status.indexing_status, tone="info")
            st.json(status.model_dump(mode="json"))
        except Exception as exc:
            handle_api_error(exc)
    if c3.button("Indexing visibility") and document_id:
        try:
            visibility = client.documents.get_indexing_visibility(document_id)
            st.metric("Failed chunks", visibility.failed_chunk_count)
            render_records_table([c.model_dump() for c in visibility.failed_chunks])
        except Exception as exc:
            handle_api_error(exc)
    if c4.button("Explore chunks") and document_id:
        try:
            chunks = client.documents.list_chunks(document_id)
            render_records_table([c.model_dump() for c in chunks.chunks])
        except Exception as exc:
            handle_api_error(exc)
    if st.button("View chunk detail") and document_id and chunk_id:
        try:
            chunk = client.documents.get_chunk(document_id, chunk_id)
            st.text_area("Chunk text", chunk.text, height=240)
        except Exception as exc:
            handle_api_error(exc)
    if has_permission(role, "documents.write") and st.button("Delete document", type="primary") and document_id:
        try:
            client.documents.delete_document(document_id)
            show_success("Document deleted.")
            record_activity("Document deleted", document_id)
        except Exception as exc:
            handle_api_error(exc)

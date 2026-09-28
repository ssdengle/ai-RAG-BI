from __future__ import annotations

import sys
from pathlib import Path

# Streamlit only knows about the folder the script is in, these lines add the repo root to python's search path
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import streamlit as st  # noqa: E402

from apps.web.streamlit_app.api_client.client import ApiClient, ApiClientError  # noqa: E402

st.set_page_config(page_title="AI Business Intelligence Platform", layout="wide")


@st.cache_resource
def get_client() -> ApiClient:
    return ApiClient()


def render_sidebar(client: ApiClient) -> bool:
    """Show dependency health; returns False when the API cannot be reached at all."""
    st.sidebar.title("System status")
    st.sidebar.caption(f"API: {client.base_url}")
    try:
        readiness = client.readiness()
    except ApiClientError:
        st.sidebar.error("API offline")
        return False

    overall = readiness.get("status", "unknown")
    if overall == "ok":
        st.sidebar.success("API is ready")
    else:
        st.sidebar.warning(f"API status: {overall}")
    for name, check in readiness.get("checks", {}).items():
        label = "Connected" if check.get("status") == "ok" else "Not Connected"
        st.sidebar.write(f"{name}: {label}")
    return True


def render_knowledge_base(client: ApiClient) -> None:
    st.subheader("Knowledge base")

    try:
        stats = client.knowledge_base_stats()
        cols = st.columns(4)
        cols[0].metric("Documents", stats["total_documents"])
        cols[1].metric("Chunks", stats["total_chunks"])
        cols[2].metric("Indexed chunks", stats["indexed_chunks"])
        cols[3].metric("Avg chunks / doc", f"{stats['average_chunks_per_document']:.1f}")
    except ApiClientError as exc:
        st.error(f"Could not load statistics: {exc.message}")

    with st.form("upload_form", clear_on_submit=True):
        st.markdown("**Upload a document** (PDF, DOCX, TXT, HTML, Markdown)")
        uploaded = st.file_uploader(
            "File",
            type=["pdf", "docx", "txt", "md", "markdown", "html", "htm"],
            label_visibility="collapsed",
        )
        col_company, col_type, col_tags = st.columns(3)
        company = col_company.text_input("Company (optional)")
        document_type = col_type.text_input(
            "Document type (optional)", placeholder="e.g. annual_report"
        )
        tags = col_tags.text_input("Tags (optional, comma-separated)")
        index_now = st.checkbox(
            "Index for search right after upload (needs LLM_API_KEY)", value=True
        )
        submitted = st.form_submit_button("Upload")

    if submitted:
        if uploaded is None:
            st.warning("Choose a file first.")
        else:
            upload_document(client, uploaded, company, document_type, tags, index_now)

    try:
        listing = client.list_documents()
    except ApiClientError as exc:
        st.error(f"Could not load documents: {exc.message}")
        return

    documents = listing.get("items", [])
    if not documents:
        st.info("No documents yet. Upload one above to get started.")
        return

    st.markdown(f"**Documents** ({listing.get('total', len(documents))} total)")
    st.dataframe(
        [
            {
                "Title": doc.get("title") or doc["filename"],
                "Company": doc.get("company") or "",
                "Type": doc.get("document_type") or "",
                "Chunks": doc["chunk_count"],
                "Status": doc["indexing_status"],
                "Uploaded": doc["created_at"][:19].replace("T", " "),
            }
            for doc in documents
        ],
        hide_index=True,
    )

    unindexed = [doc for doc in documents if doc["indexing_status"] != "indexed"]
    if unindexed:
        labels = {doc["document_id"]: doc.get("title") or doc["filename"] for doc in unindexed}
        col_select, col_button = st.columns([3, 1])
        selected = col_select.selectbox(
            "Index a document", options=list(labels), format_func=labels.get
        )
        col_button.write("")
        if col_button.button("Index"):
            index_document(client, selected)


def upload_document(client, uploaded, company, document_type, tags, index_now) -> None:
    with st.spinner(f"Uploading {uploaded.name}..."):
        try:
            document = client.upload_document(
                filename=uploaded.name,
                content=uploaded.getvalue(),
                content_type=uploaded.type,
                company=company.strip() or None,
                document_type=document_type.strip() or None,
                tags=tags.strip() or None,
            )
        except ApiClientError as exc:
            st.error(f"Upload failed: {exc.message}")
            return
    st.success(f"Uploaded {document['filename']} ({document['chunk_count']} chunks).")
    if index_now:
        index_document(client, document["document_id"])


def index_document(client: ApiClient, document_id: str) -> None:
    with st.spinner("Generating embeddings..."):
        try:
            result = client.index_document(document_id)
        except ApiClientError as exc:
            st.error(f"Indexing failed: {exc.message}")
            return
    st.success(f"Indexed {result['embedding_count']} chunks.")


def render_ask(client: ApiClient) -> None:
    st.subheader("Ask a question")
    st.caption("Answers are generated only from indexed documents, with citations.")

    with st.form("ask_form"):
        question = st.text_area(
            "Question", placeholder="What are the main risks mentioned in the annual report?"
        )
        col_mode, col_top_k = st.columns(2)
        mode = col_mode.selectbox("Retrieval mode", ["hybrid", "semantic", "keyword"])
        top_k = col_top_k.slider("Sources to retrieve", min_value=1, max_value=20, value=5)
        submitted = st.form_submit_button("Ask")

    if not submitted:
        return
    if not question.strip():
        st.warning("Enter a question first.")
        return

    with st.spinner("Thinking..."):
        try:
            result = client.ask_question(query=question.strip(), mode=mode, top_k=top_k)
        except ApiClientError as exc:
            st.error(f"Question failed: {exc.message}")
            return

    st.markdown("### Answer")
    st.write(result["answer"])
    st.caption(
        f"Confidence: {result['confidence']:.0%} · Model: {result.get('llm_model') or 'n/a'}"
    )

    citations = result.get("citations", [])
    if citations:
        st.markdown("### Sources")
        for number, citation in enumerate(citations, start=1):
            page = f", page {citation['page_number']}" if citation.get("page_number") else ""
            with st.expander(
                f"[{number}] {citation.get('title') or citation['document_id']}{page}"
            ):
                st.write(citation["snippet"])
                st.caption(f"Relevance score: {citation['score']:.3f}")


def main() -> None:
    client = get_client()
    st.title("AI Business Intelligence Platform")
    if not render_sidebar(client):
        st.error(
            f"Cannot reach the backend API at {client.base_url}. "
            "Start it with `docker compose up` or set API_BASE_URL."
        )
        st.stop()

    tab_kb, tab_ask = st.tabs(["Knowledge base", "Ask a question"])
    with tab_kb:
        render_knowledge_base(client)
    with tab_ask:
        render_ask(client)


main()

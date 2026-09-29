from __future__ import annotations

from typing import Iterable

import streamlit as st

from apps.web.streamlit_app.api_client.models import CitationModel
from apps.web.streamlit_app.components.ui import escape, html_block
from apps.web.streamlit_app.utils.formatting import format_score, truncate_text


def citation_card_html(citation: CitationModel, index: int) -> str:
    page = f" · Page {citation.page_number}" if citation.page_number else ""
    return f"""
    <div class="citation-card">
        <div class="citation-card-title">[{index}] {escape(citation.title or citation.document_id)}</div>
        <div class="citation-card-meta">Chunk {escape(citation.chunk_id)}{page} · Score {format_score(citation.score)}</div>
        <div class="citation-card-snippet">{escape(truncate_text(citation.snippet, 280))}</div>
    </div>
    """


def render_citations(citations: Iterable[CitationModel]) -> None:
    items = list(citations)
    if not items:
        html_block('<div class="empty-state-desc">No citations available for this response.</div>')
        return
    html_block("".join(citation_card_html(item, idx) for idx, item in enumerate(items, start=1)))


def render_citation_accordion(citations: Iterable[CitationModel]) -> None:
    items = list(citations)
    if not items:
        st.caption("No citations.")
        return
    with st.expander(f"Citations ({len(items)})", expanded=False):
        render_citations(items)

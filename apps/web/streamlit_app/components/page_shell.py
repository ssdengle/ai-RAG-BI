from __future__ import annotations

import streamlit as st

from apps.web.streamlit_app.components.layout import apply_page_config, inject_styles, render_breadcrumb, render_page_header
from apps.web.streamlit_app.components.navigation import render_sidebar_navigation
from apps.web.streamlit_app.utils.session import ensure_token_fresh, init_session_state, is_authenticated


def bootstrap_page(
    title: str,
    subtitle: str,
    *,
    active_page: str | None = None,
    breadcrumb: list[tuple[str, str | None]] | None = None,
) -> None:
    apply_page_config(title)
    init_session_state()
    inject_styles()
    if not is_authenticated():
        st.switch_page("app.py")
    ensure_token_fresh()
    render_sidebar_navigation(active_page=active_page)
    if breadcrumb:
        render_breadcrumb(breadcrumb)
    render_page_header(title, subtitle)

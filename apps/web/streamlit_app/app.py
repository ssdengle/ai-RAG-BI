"""Main Streamlit entry point — login gate and session bootstrap."""

from __future__ import annotations

import streamlit as st

from apps.web.streamlit_app.components.auth import render_login_form
from apps.web.streamlit_app.components.layout import apply_page_config, inject_styles
from apps.web.streamlit_app.utils.session import init_session_state, is_authenticated

apply_page_config("Sign In")
init_session_state()
inject_styles()

if not is_authenticated():
    if render_login_form():
        st.rerun()
    st.stop()

st.switch_page("pages/01_Dashboard.py")

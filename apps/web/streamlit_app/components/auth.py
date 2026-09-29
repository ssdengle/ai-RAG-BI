from __future__ import annotations

import streamlit as st

from apps.web.streamlit_app.components.cards import empty_state
from apps.web.streamlit_app.components.notifications import show_error, show_success
from apps.web.streamlit_app.components.ui import html_block, icon
from apps.web.streamlit_app.utils.session import is_authenticated, login_with_api_key, login_with_password


def render_login_form() -> bool:
    html_block(
        f"""
        <div class="hero-banner" style="max-width:520px;margin:2rem auto 1.5rem;">
            <div class="hero-title" style="font-size:1.45rem;">Nexus AI Platform</div>
            <div class="hero-subtitle">Enterprise intelligence console for RAG, workflows, and evaluation.</div>
        </div>
        """
    )

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        tab_password, tab_api_key = st.tabs(["Credentials", "API Key"])

        with tab_password:
            with st.form("login_form"):
                username = st.text_input("Username", value="analyst")
                password = st.text_input("Password", type="password", value="change-me")
                submitted = st.form_submit_button("Sign in to platform", use_container_width=True, type="primary")
                if submitted:
                    try:
                        login_with_password(username, password)
                        show_success("Authentication successful.")
                        return True
                    except Exception as exc:
                        show_error(str(exc))

        with tab_api_key:
            with st.form("api_key_form"):
                api_key = st.text_input("API Key", type="password")
                role = st.selectbox("Role", ["viewer", "analyst", "reviewer", "admin"])
                submitted = st.form_submit_button("Connect with API key", use_container_width=True)
                if submitted and api_key:
                    login_with_api_key(api_key, role=role)
                    show_success("Connected with API key.")
                    return True

    if not is_authenticated():
        empty_state("Secure access required", "Sign in to access the enterprise AI platform.", icon_name="lock")

    return is_authenticated()

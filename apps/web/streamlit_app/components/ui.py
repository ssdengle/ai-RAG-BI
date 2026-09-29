from __future__ import annotations

import html
from pathlib import Path

import streamlit as st

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


def icon(name: str, *, size: str = "1.125rem") -> str:
    """Render a Material Symbols Outlined icon."""
    safe = html.escape(name)
    return f'<span class="material-symbols-outlined" style="font-size:{size}">{safe}</span>'


def load_theme() -> None:
    """Inject centralized CSS design system."""
    variables = (_ASSETS_DIR / "variables.css").read_text(encoding="utf-8")
    theme = (_ASSETS_DIR / "theme.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{variables}\n{theme}</style>", unsafe_allow_html=True)


def html_block(content: str) -> None:
    st.markdown(content, unsafe_allow_html=True)


def escape(text: str | int | float | None) -> str:
    if text is None:
        return "—"
    return html.escape(str(text))

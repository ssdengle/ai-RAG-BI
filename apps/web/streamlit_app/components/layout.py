from __future__ import annotations

import streamlit as st

from apps.web.streamlit_app.components.ui import escape, html_block, icon, load_theme


def apply_page_config(title: str) -> None:
    st.set_page_config(
        page_title=f"{title} | Nexus AI Platform",
        page_icon="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect fill='%233b82f6' rx='20' width='100' height='100'/></svg>",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def inject_styles() -> None:
    load_theme()


def render_breadcrumb(items: list[tuple[str, str | None]]) -> None:
    parts = []
    for label, _href in items:
        parts.append(f"<span>{escape(label)}</span>")
    html = '<div class="breadcrumb">' + ' <span>/</span> '.join(parts[:-1]) + (
        f' <span>/</span> <span class="active">{escape(items[-1][0])}</span>' if items else ""
    ) + "</div>"
    html_block(html)


def render_page_header(title: str, subtitle: str) -> None:
    html_block(
        f"""
        <div class="page-header">
            <h1>{escape(title)}</h1>
            <p>{escape(subtitle)}</p>
        </div>
        """
    )


def render_hero_banner(
    *,
    title: str,
    subtitle: str,
    username: str,
    environment: str,
    health_status: str,
) -> None:
    html_block(
        f"""
        <div class="hero-banner">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:1rem;">
                <div>
                    <div class="hero-title">{escape(title)}</div>
                    <div class="hero-subtitle">{escape(subtitle)}</div>
                </div>
                <div style="display:flex;gap:0.5rem;flex-wrap:wrap;">
                    <span class="badge badge-primary">{escape(username)}</span>
                    <span class="badge badge-neutral">{escape(environment)}</span>
                    <span class="badge badge-success">{escape(health_status)}</span>
                </div>
            </div>
        </div>
        """
    )


def render_section_header(title: str, *, action: str | None = None) -> None:
    action_html = f'<span style="color:var(--color-text-subtle);font-size:0.8rem;">{escape(action)}</span>' if action else ""
    html_block(
        f"""
        <div class="section-header">
            <h2>{escape(title)}</h2>
            {action_html}
        </div>
        """
    )


def render_toolbar(content_html: str) -> None:
    html_block(f'<div class="toolbar">{content_html}</div>')


def glass_container_start() -> None:
    html_block('<div class="glass-card">')


def glass_container_end() -> None:
    html_block("</div>")

from __future__ import annotations

import streamlit as st

from apps.web.streamlit_app.components.ui import escape, html_block, icon


def metric_card_html(
    *,
    label: str,
    value: str | int | float,
    icon_name: str = "analytics",
    delta: str | None = None,
    delta_positive: bool | None = None,
) -> str:
    delta_class = ""
    if delta_positive is True:
        delta_class = " positive"
    elif delta_positive is False:
        delta_class = " negative"
    delta_html = f'<div class="metric-card-delta{delta_class}">{escape(delta)}</div>' if delta else ""
    return f"""
    <div class="metric-card">
        <div class="metric-card-header">
            <div class="metric-card-label">{escape(label)}</div>
            <div class="metric-card-icon">{icon(icon_name)}</div>
        </div>
        <div class="metric-card-value">{escape(value)}</div>
        {delta_html}
    </div>
    """


def render_metric_card(
    column,
    *,
    label: str,
    value: str | int | float,
    icon_name: str = "analytics",
    delta: str | None = None,
    delta_positive: bool | None = None,
) -> None:
    column.markdown(
        metric_card_html(
            label=label,
            value=value,
            icon_name=icon_name,
            delta=delta,
            delta_positive=delta_positive,
        ),
        unsafe_allow_html=True,
    )


def info_card(title: str, body: str, *, icon_name: str = "info") -> None:
    html_block(
        f"""
        <div class="glass-card">
            <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.5rem;">
                {icon(icon_name)}
                <strong style="color:var(--color-text);">{escape(title)}</strong>
            </div>
            <div style="color:var(--color-text-muted);font-size:0.88rem;line-height:1.5;">{escape(body)}</div>
        </div>
        """
    )


def action_card(title: str, description: str, *, icon_name: str = "bolt") -> str:
    return f"""
    <div class="action-card">
        <div style="display:flex;align-items:center;gap:0.45rem;margin-bottom:0.35rem;">
            {icon(icon_name)}
            <div class="action-card-title">{escape(title)}</div>
        </div>
        <div class="action-card-desc">{escape(description)}</div>
    </div>
    """


def render_action_cards(items: list[tuple[str, str, str]]) -> None:
    cols = st.columns(min(len(items), 4))
    for idx, (title, desc, icon_name) in enumerate(items):
        cols[idx % len(cols)].markdown(action_card(title, desc, icon_name=icon_name), unsafe_allow_html=True)


def document_card(
    *,
    filename: str,
    document_id: str,
    company: str | None,
    status: str,
    chunk_count: int,
) -> None:
    html_block(
        f"""
        <div class="glass-card" style="margin-bottom:0.75rem;">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                <div>
                    <div style="font-weight:600;color:var(--color-text);">{escape(filename)}</div>
                    <div style="font-size:0.75rem;color:var(--color-text-subtle);margin-top:0.2rem;">{escape(document_id)}</div>
                </div>
                <span class="badge badge-neutral">{escape(status)}</span>
            </div>
            <div style="margin-top:0.65rem;font-size:0.8rem;color:var(--color-text-muted);">
                {escape(company or "—")} · {chunk_count} chunks
            </div>
        </div>
        """
    )


def workflow_card(*, workflow_id: str, topic: str, status: str) -> None:
    html_block(
        f"""
        <div class="glass-card" style="margin-bottom:0.65rem;">
            <div style="font-weight:600;color:var(--color-text);">{escape(topic)}</div>
            <div style="font-size:0.75rem;color:var(--color-text-subtle);">{escape(workflow_id)}</div>
            <div style="margin-top:0.5rem;"><span class="badge badge-info">{escape(status)}</span></div>
        </div>
        """
    )


def empty_state(title: str, description: str, *, icon_name: str = "inbox") -> None:
    html_block(
        f"""
        <div class="empty-state">
            <div class="empty-state-icon">{icon(icon_name, size="2.5rem")}</div>
            <div class="empty-state-title">{escape(title)}</div>
            <div class="empty-state-desc">{escape(description)}</div>
        </div>
        """
    )


def activity_feed(items: list[dict]) -> None:
    if not items:
        empty_state("No recent activity", "Actions you take in this session will appear here.", icon_name="history")
        return
    parts = ['<div class="timeline">']
    for item in items:
        parts.append(
            f"""
            <div class="timeline-item">
                <div class="timeline-title">{escape(item.get("title", ""))}</div>
                <div class="timeline-meta">{escape(item.get("detail", ""))}</div>
            </div>
            """
        )
    parts.append("</div>")
    html_block("".join(parts))

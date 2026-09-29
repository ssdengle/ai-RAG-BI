from __future__ import annotations

from typing import Any

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

CHART_COLORS = ["#3b82f6", "#06b6d4", "#6366f1", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"]
CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#94a3b8", family="Inter, sans-serif", size=12),
    margin=dict(l=16, r=16, t=36, b=16),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)


def _apply_layout(fig: go.Figure, title: str) -> go.Figure:
    fig.update_layout(**CHART_LAYOUT, title=dict(text=title, font=dict(color="#f1f5f9", size=14)))
    fig.update_xaxes(gridcolor="rgba(148,163,184,0.08)", zerolinecolor="rgba(148,163,184,0.08)")
    fig.update_yaxes(gridcolor="rgba(148,163,184,0.08)", zerolinecolor="rgba(148,163,184,0.08)")
    return fig


def bar_chart(data: dict[str, float], title: str) -> None:
    if not data:
        st.caption("No chart data.")
        return
    fig = px.bar(x=list(data.keys()), y=list(data.values()), color_discrete_sequence=CHART_COLORS)
    _apply_layout(fig, title)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def line_chart(series: dict[str, list[float]], title: str) -> None:
    if not series:
        st.caption("No chart data.")
        return
    fig = go.Figure()
    for idx, (name, values) in enumerate(series.items()):
        fig.add_trace(
            go.Scatter(
                x=list(range(len(values))),
                y=values,
                mode="lines+markers",
                name=name,
                line=dict(color=CHART_COLORS[idx % len(CHART_COLORS)], width=2),
            )
        )
    _apply_layout(fig, title)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def area_chart(x: list[Any], y: list[float], title: str) -> None:
    fig = go.Figure(data=go.Scatter(x=x, y=y, fill="tozeroy", line=dict(color="#3b82f6")))
    _apply_layout(fig, title)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def pie_chart(data: dict[str, float], title: str) -> None:
    if not data:
        st.caption("No chart data.")
        return
    fig = px.pie(names=list(data.keys()), values=list(data.values()), color_discrete_sequence=CHART_COLORS, hole=0.45)
    _apply_layout(fig, title)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def radar_chart(categories: list[str], values: list[float], title: str) -> None:
    if not categories:
        st.caption("No chart data.")
        return
    fig = go.Figure(
        data=go.Scatterpolar(
            r=values + [values[0]],
            theta=categories + [categories[0]],
            fill="toself",
            line=dict(color="#06b6d4"),
            fillcolor="rgba(6,182,212,0.25)",
        )
    )
    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(visible=True, gridcolor="rgba(148,163,184,0.12)", color="#64748b"),
            angularaxis=dict(gridcolor="rgba(148,163,184,0.12)", color="#94a3b8"),
        ),
        **CHART_LAYOUT,
        title=dict(text=title, font=dict(color="#f1f5f9", size=14)),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def gauge_chart(value: float, title: str, *, max_value: float = 100) -> None:
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            title={"text": title, "font": {"color": "#f1f5f9", "size": 14}},
            gauge={
                "axis": {"range": [0, max_value], "tickcolor": "#64748b"},
                "bar": {"color": "#3b82f6"},
                "bgcolor": "rgba(17,24,39,0.8)",
                "bordercolor": "rgba(148,163,184,0.2)",
                "steps": [
                    {"range": [0, max_value * 0.5], "color": "rgba(239,68,68,0.15)"},
                    {"range": [max_value * 0.5, max_value * 0.8], "color": "rgba(245,158,11,0.15)"},
                    {"range": [max_value * 0.8, max_value], "color": "rgba(16,185,129,0.15)"},
                ],
            },
        )
    )
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#94a3b8"), height=280, margin=dict(l=20, r=20, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def heatmap(data: dict[str, dict[str, float]], title: str) -> None:
    if not data:
        st.caption("No chart data.")
        return
    rows = list(data.keys())
    cols = sorted({col for row in data.values() for col in row.keys()})
    matrix = [[row.get(col, 0.0) for col in cols] for row in [data[r] for r in rows]]
    fig = go.Figure(data=go.Heatmap(z=matrix, x=cols, y=rows, colorscale="Blues"))
    _apply_layout(fig, title)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_timeline(events: list[dict[str, Any]]) -> None:
    from apps.web.streamlit_app.components.cards import activity_feed

    activity_feed(
        [
            {
                "title": f"{event.get('agent', 'agent')} · {event.get('event_type', '')}",
                "detail": event.get("message", ""),
            }
            for event in events
        ]
    )


def render_failure_mode_chart(summary: dict[str, int]) -> None:
    bar_chart({key: float(value) for key, value in summary.items()}, "Failure Modes")


def render_scorer_chart(scorer_averages: dict[str, float]) -> None:
    bar_chart(scorer_averages, "Scorer Averages")

"""Metrics card — a thin wrapper over st.metric that supports a help tooltip
and a colored left border to match risk semantics.
"""
import streamlit as st


def render(
    label: str,
    value: str | int | float,
    delta: str | None = None,
    help: str | None = None,
    accent: str = "#1f77b4",
) -> None:
    """Render a styled metric card. Use inside a column."""
    st.markdown(
        f"""
        <div style="
            border-left: 4px solid {accent};
            padding: 8px 14px;
            background: rgba(127,127,127,0.04);
            border-radius: 4px;
            margin-bottom: 6px;
        ">
            <div style="font-size:0.85rem; color:#666;">{label}</div>
            <div style="font-size:1.7rem; font-weight:700;">{value}</div>
            {f'<div style="font-size:0.85rem; color:#888;">{delta}</div>' if delta else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )
    if help:
        st.caption(help)

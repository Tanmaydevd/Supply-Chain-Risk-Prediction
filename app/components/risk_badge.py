"""Risk badge — colored pill-shaped HTML badge for High/Medium/Low risk."""
import streamlit as st


_COLORS = {
    "High": ("#ffe1e1", "#b00020"),      # bg, text
    "Medium": ("#fff4d6", "#a05a00"),
    "Low": ("#dff5e1", "#1e6f3a"),
}


def render(level: str, score: int | None = None) -> None:
    """Render a colored risk badge inline. Falls back to plain text on unknown level."""
    bg, fg = _COLORS.get(level, ("#eeeeee", "#444"))
    label = f"{level}" if score is None else f"{level} ({score})"
    st.markdown(
        f"""
        <span style="
            display:inline-block;
            padding:6px 14px;
            border-radius:999px;
            background:{bg};
            color:{fg};
            font-weight:600;
            font-size:0.95rem;
            letter-spacing:0.02em;
        ">{label}</span>
        """,
        unsafe_allow_html=True,
    )

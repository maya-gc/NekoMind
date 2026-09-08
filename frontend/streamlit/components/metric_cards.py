"""Cards de metricas do NekoMind."""
from __future__ import annotations

import streamlit as st

CARD_CSS = """
<style>
.neko-metric {
    background: linear-gradient(150deg, #ffffff 0%, #fdf3f8 100%);
    border: 1px solid #f3c9db;
    border-radius: 16px;
    padding: 0.9rem 1rem;
    box-shadow: 0 2px 6px rgba(176, 106, 131, 0.08);
}
.neko-metric .label { font-size: 0.78rem; color: #b06a83; font-weight: 600;
                      text-transform: uppercase; letter-spacing: 0.05em; }
.neko-metric .value { font-size: 1.7rem; font-weight: 800; color: #7a4a5b; }
.neko-metric .unit  { font-size: 0.85rem; color: #b98ba0; }
</style>
"""


def metric_card(label: str, value: str, unit: str = "", key: str = "") -> None:
    st.markdown(
        f'<div class="neko-metric">'
        f'<div class="label">{label}</div>'
        f'<div class="value">{value} <span class="unit">{unit}</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def show_metric_cards(summary: dict) -> None:
    """Cards principais do dashboard a partir do resumo do backend."""
    st.markdown(CARD_CSS, unsafe_allow_html=True)

    total_minutes = summary.get("total_study_seconds", 0) / 60.0
    clarity = summary.get("avg_clarity_score")
    top = summary.get("top_topics", [])

    cols = st.columns(4)
    with cols[0]:
        metric_card("Sessões", f"{summary.get('total_sessions', 0)}", "total")
    with cols[1]:
        metric_card("Tempo estudado", f"{total_minutes:.1f}", "min")
    with cols[2]:
        metric_card(
            "Clareza média",
            f"{clarity:.1f}" if clarity is not None else "—",
            "/ 10",
        )
    with cols[3]:
        metric_card(
            "Tópicos frequentes",
            f"{len(top)}",
            "mais citados",
        )
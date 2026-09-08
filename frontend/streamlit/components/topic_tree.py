"""Arvore de topicos de uma sessao (visualizacao simples)."""
from __future__ import annotations

import streamlit as st

TOPIC_COLORS = ["#f6a5c0", "#f9c5d5", "#fbd3e3", "#fdeef5"]


def render_topic_tree(topics: list[dict], session_title: str | None) -> None:
    """Mostra a sessao como raiz e os topicos como folhas."""
    if not topics:
        st.caption("Nenhum tópico extraído nesta sessão.")
        return

    title = session_title or "Sessão"
    st.markdown(f"**🐱 {title}**")
    for i, topic in enumerate(topics):
        relevance = float(topic.get("relevance", 1.0))
        pct = int(relevance * 100)
        color = TOPIC_COLORS[i % len(TOPIC_COLORS)]
        st.markdown(
            f'<span style="color:{color};font-weight:700;">└─</span> '
            f'<b>{topic["name"]}</b> '
            f'<span style="color:#b98ba0;">· relevância {pct}%</span>',
            unsafe_allow_html=True,
        )
        if topic.get("notes"):
            st.caption(f"   {topic['notes']}")
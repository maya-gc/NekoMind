"""Página Tópicos: conceitos extraídos das sessões."""
from __future__ import annotations

import streamlit as st

from components.topic_tree import render_topic_tree
from services import backend_client

st.markdown("## 🧠 Tópicos")

sessions = backend_client.list_sessions(limit=100)
if not sessions:
    st.caption("Nenhuma sessão registrada.")
    st.stop()

all_topics = []
for s in sessions:
    detail = backend_client.get_session(s["id"]) or {}
    for topic in detail.get("topics", []):
        all_topics.append(
            {
                "name": topic["name"],
                "relevance": topic.get("relevance", 1.0),
                "session_id": s["id"],
                "session_title": s.get("title"),
                "notes": topic.get("notes"),
            }
        )

if not all_topics:
    st.info("Nenhum tópico extraído ainda. Crie uma sessão de demonstração.")
    st.stop()

from collections import Counter

counts = Counter(t["name"] for t in all_topics)
st.markdown("### 🔥 Tópicos mais citados")
for name, n in counts.most_common(8):
    st.markdown(f"- **{name}** — {n} vez(es)")

st.markdown("### 🌳 Tópicos por sessão")
expandido = st.checkbox("Expandir todas as sessões")
for session_id in sorted({t["session_id"] for t in all_topics}):
    topics = [t for t in all_topics if t["session_id"] == session_id]
    title = next(t["session_title"] for t in topics if t["session_title"]) or "Sessão"
    with st.expander(f"#{session_id} · {title}", expanded=expandido):
        render_topic_tree(topics, title)
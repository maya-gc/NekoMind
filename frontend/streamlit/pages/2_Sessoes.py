"""Página Sessões: lista, detalhe e transcrição."""
from __future__ import annotations

import streamlit as st

from components.avatar_widget import render_avatar
from components.topic_tree import render_topic_tree
from services import backend_client

st.markdown("## 📚 Sessões")

if st.button("➕ Nova sessão (demo)", use_container_width=True):
    with st.spinner("Criando e analisando sessão de demonstração..."):
        try:
            backend_client.demo_session()
            st.success("Sessão de demonstração criada! 🐾")
            st.rerun()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Falha ao criar demonstração: {exc}")

sessions = backend_client.list_sessions(limit=100)
if not sessions:
    st.caption("Nenhuma sessão registrada.")
    st.stop()

options = {f"#{s['id']} · {s['title'] or 'Sem título'} · {s['status']}": s["id"]
           for s in sessions}
label = st.selectbox("Selecione uma sessão", list(options.keys()))
session_id = options[label]

detail = backend_client.get_session(session_id)
if not detail:
    st.error("Sessão não encontrada.")
    st.stop()

# Status para o avatar (espelha o firmware).
status_map = {
    "recording": "RECORDING",
    "processing": "PROCESSING",
    "completed": "SUCCESS",
    "error": "ERROR",
}
render_avatar(
    status_map.get(detail["status"], "IDLE"),
    caption=f"Sessão #{detail['id']} · {detail['status']}",
)

if detail.get("is_demo"):
    st.caption("⚠️ Dados de demonstração (adapter mock do backend).")

metrics = {m["name"]: m for m in detail.get("metrics", [])}
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Duração", f"{detail.get('duration_seconds', 0):.1f} s")
with col2:
    clarity = detail.get("clarity_score")
    st.metric("Clareza", f"{clarity:.1f}" if clarity is not None else "—", "/ 10")
with col3:
    words = metrics.get("word_count", {}).get("value", 0)
    st.metric("Palavras", f"{words:.0f}")

if metrics:
    st.markdown("#### Métricas detalhadas")
    for name, m in metrics.items():
        unit = m.get("unit") or ""
        st.markdown(f"- **{name}**: {m['value']} {unit}")

st.markdown("#### 📝 Transcrição")
st.text_area(
    "transcrição",
    detail.get("transcription") or "(sem transcrição)",
    height=160,
    label_visibility="collapsed",
)

render_topic_tree(detail.get("topics", []), detail.get("title"))
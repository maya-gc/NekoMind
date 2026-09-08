"""Página Dashboard: visão geral do estudante."""
from __future__ import annotations

import streamlit as st

from components.avatar_widget import render_avatar
from components.metric_cards import show_metric_cards
from components.session_chart import clarity_trend, duration_chart
from services import backend_client

st.markdown("## 📊 Dashboard")

try:
    health = backend_client.health()
    if health.get("status") != "ok":
        st.error(f"Backend indisponível: {health}")
        st.stop()
except Exception as exc:  # noqa: BLE001
    st.error(f"Não foi possível conectar ao backend: {exc}")
    st.info("Confira a URL em **Configurações** ou inicie o backend.")
    st.stop()

if backend_client.is_demo_mode():
    st.info("Modo demonstração ativo — os dados abaixo podem ser [DEMO].")

summary = backend_client.dashboard_summary()
show_metric_cards(summary)

if summary.get("top_topics"):
    st.markdown("### 🧠 Tópicos mais frequentes")
    for name, count in summary["top_topics"]:
        st.progress(1.0, text=f"{name} · {count} menção(ões)")

st.markdown("### 📈 Evolução")
sessions = backend_client.list_sessions(limit=50)
if sessions:
    left, right = st.columns(2)
    with left:
        st.markdown("**Clareza por sessão**")
        clarity_trend(sessions)
    with right:
        st.markdown("**Duração por sessão**")
        duration_chart(sessions)
else:
    st.caption("Nenhuma sessão ainda. Crie uma demonstração na página Sessões.")
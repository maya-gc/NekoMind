"""Página Dashboard: visão geral do estudante."""

from __future__ import annotations

import streamlit as st
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

backend_status = backend_client.effective_backend_status()
if backend_status.get("is_demo") is True:
    st.warning(
        "Backend em demonstração — resultados mock aparecem identificados como [DEMO]."
    )
elif backend_status.get("is_demo") is None:
    st.info(
        "Modo do backend desconhecido; confira a página Configurações antes de interpretar resultados."
    )

summary = backend_client.dashboard_summary()
show_metric_cards(summary)
st.caption(
    "Métricas do dashboard são heurísticas de apoio à reflexão; não comprovam conhecimento ou correção factual."
)

if summary.get("top_topics"):
    st.markdown("### 🧠 Tópicos mais frequentes")
    for name, count in summary["top_topics"]:
        st.progress(1.0, text=f"{name} · {count} menção(ões)")

st.markdown("### 📈 Evolução")
sessions = backend_client.list_sessions(limit=50)
demo_count = sum(1 for session in sessions if session.get("is_demo"))
if demo_count:
    st.caption(f"Inclui {demo_count} sessão(ões) de demonstração identificada(s).")
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

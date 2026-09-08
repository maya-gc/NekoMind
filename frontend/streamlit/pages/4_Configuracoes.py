"""Página Configurações: URL do backend e modo de demonstração."""
from __future__ import annotations

import streamlit as st

from services import backend_client

st.markdown("## ⚙️ Configurações")

st.markdown("#### Conexão com o backend")
url = st.text_input(
    "URL do backend",
    value=backend_client.get_backend_url(),
    help="Endereço da API FastAPI (padrão http://127.0.0.1:8000).",
)
if st.button("Salvar URL"):
    st.session_state["backend_url"] = url.strip() or "http://127.0.0.1:8000"
    st.success("URL salva.")

st.markdown("#### Modo de demonstração")
st.session_state["demo_mode"] = st.toggle(
    "Usar dados de demonstração",
    value=backend_client.is_demo_mode(),
    help="Quando ativo, o dashboard destaca quando os dados vêm dos "
    "adapters mock [DEMO] do backend.",
)

st.markdown("#### Conexão atual")
try:
    health = backend_client.health()
    st.json(health)
except Exception as exc:  # noqa: BLE001
    st.error(f"Sem conexão com o backend: {exc}")

st.markdown("---")
st.caption(
    "O NekoMind usa processamento por IA como apoio à reflexão do "
    "estudante, não como avaliação pedagógica definitiva. Métricas de "
    "clareza e abrangência são heurísticas e devem ser tratadas como "
    "estimativas."
)
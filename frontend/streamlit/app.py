"""NekoMind - Dashboard de apoio ao estudo (técnica Feynman).

Frontend do MVP: consome somente a API do backend
(frontend/streamlit/services/backend_client.py).
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="NekoMind",
    page_icon="🐱",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .neko-header {
        font-size: 2.2rem; font-weight: 800;
        color: #7a4a5b; margin-bottom: 0;
    }
    .neko-sub { color: #b06a83; font-size: 1rem; margin-top: -0.4rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="neko-header">🐱 NekoMind</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="neko-sub">apoio à reflexão do estudante · técnica Feynman</div>',
    unsafe_allow_html=True,
)

# Estado de configuracao com defaults.
if "backend_url" not in st.session_state:
    st.session_state["backend_url"] = "http://127.0.0.1:8000"

st.sidebar.markdown("## 🗂 Navegação")
st.sidebar.markdown(
    """
    - **1. Dashboard** — visão geral
    - **2. Sessões** — histórico e detalhes
    - **3. Tópicos** — conceitos extraídos
    - **4. Configurações** — backend e modo efetivo
    """
)
st.sidebar.caption(
    "ℹ️ O processamento por IA é apoio à reflexão, não avaliação definitiva. "
    "Métricas de clareza e abrangência são heurísticas (estimativas)."
)

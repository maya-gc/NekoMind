"""Graficos de sessoes (evolucao do estudante)."""
from __future__ import annotations

import pandas as pd
import streamlit as st


def clarity_trend(sessions: list[dict]) -> None:
    """Linha da nota de clareza ao longo das sessoes."""
    rows = [
        {"sessão": s["id"], "clareza": s.get("clarity_score")}
        for s in sessions
        if s.get("clarity_score") is not None
    ]
    if not rows:
        st.caption("Ainda não há notas de clareza para exibir.")
        return
    df = pd.DataFrame(rows)
    st.line_chart(df.set_index("sessão"), color="#f6a5c0")


def duration_chart(sessions: list[dict]) -> None:
    """Barras da duracao (min) por sessao."""
    rows = [
        {"sessão": s["id"], "minutos": s.get("duration_seconds", 0) / 60.0}
        for s in sessions
    ]
    if not rows:
        return
    df = pd.DataFrame(rows)
    st.bar_chart(df.set_index("sessão"), color="#f6a5c0")
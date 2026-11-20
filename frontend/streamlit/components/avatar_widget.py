"""Widget de Lumi, mascote felina original do NekoMind, em arte ASCII/emoji.

Estados espelham o firmware (iot/nekomind_firmware): IDLE, RECORDING,
PAUSED, PROCESSING, SUCCESS, ERROR.
"""

from __future__ import annotations

import streamlit as st

AVATAR_FACES = {
    "IDLE": "(=^.^=) 🐾 aguardando...",
    "PAUSED": "(=^-^=) pausa",
    "RECORDING": "(=O.o=) 🎙 ouvindo você explicar...",
    "SENDING": "(=>^.^)=> 📡 enviando áudio...",
    "PROCESSING": "(=@.@=) 🧠 pensando...",
    "SUCCESS": "(=^*^=) ⭐ sucesso!",
    "ERROR": "(=x.x=) 😿 algo deu errado",
}

AVATAR_CSS = """
<style>
.neko-avatar {
    font-family: 'Courier New', monospace;
    font-size: 2.6rem;
    line-height: 1.3;
    text-align: center;
    padding: 1.4rem 1rem;
    border-radius: 20px;
    border: 3px dashed #32d6c4;
    background: linear-gradient(160deg, #f7f4ff 0%, #ded6ff 60%, #b8acec 100%);
    color: #332b55;
    margin-bottom: 0.6rem;
}
.neko-state {
    text-align: center;
    font-size: 0.95rem;
    color: #655a91;
    font-weight: 600;
    letter-spacing: 0.04em;
}
</style>
"""


def render_avatar(state: str, caption: str | None = None) -> None:
    """Renderiza o avatar no estado atual."""
    face = AVATAR_FACES.get(state, AVATAR_FACES["IDLE"])
    st.markdown(AVATAR_CSS, unsafe_allow_html=True)
    st.markdown(
        f'<div class="neko-avatar">{face}</div>'
        f'<div class="neko-state">{caption or state}</div>',
        unsafe_allow_html=True,
    )

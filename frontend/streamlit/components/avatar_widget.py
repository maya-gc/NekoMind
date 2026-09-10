"""Widget do avatar NekoMind (mascote gato em arte ASCII/emoji).

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
    border: 3px dashed #f6a5c0;
    background: linear-gradient(160deg, #fff7fb 0%, #fdeef5 60%, #fbd3e3 100%);
    color: #7a4a5b;
    margin-bottom: 0.6rem;
}
.neko-state {
    text-align: center;
    font-size: 0.95rem;
    color: #b06a83;
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

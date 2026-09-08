"""Servico de transcricao: usa o ASRAdapter configurado."""
from __future__ import annotations

from pathlib import Path

from app.adapters.asr_adapter import get_asr_adapter
from app.config import get_settings


def transcribe_audio(audio_path: Path | None) -> str:
    """Retorna a transcricao do audio.

    No modo mock (padrao), retorna texto ficticio marcado como [DEMO],
    independente do arquivo - ideal para desenvolvimento sem modelo de IA.
    """
    settings = get_settings()
    adapter = get_asr_adapter(settings.asr_provider)
    # No modo mock o caminho pode nem existir; o adapter ignora o conteudo.
    return adapter.transcribe(audio_path or Path(""))

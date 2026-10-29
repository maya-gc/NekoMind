"""Servico de transcricao: usa o ASRAdapter configurado."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.adapters.asr_adapter import get_asr_adapter
from app.config import get_settings


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    provider: str
    is_demo: bool


def transcribe_audio(audio_path: Path | None) -> str:
    """Retorna a transcricao do audio.

    No modo mock (padrao), retorna texto ficticio marcado como [DEMO],
    independente do arquivo - ideal para desenvolvimento sem modelo de IA.
    """
    return transcribe_audio_result(audio_path).text


def transcribe_audio_result(
    audio_path: Path | None,
    *,
    provider: str | None = None,
) -> TranscriptionResult:
    settings = get_settings()
    adapter = get_asr_adapter(
        provider or settings.asr_provider,
        settings.asr_model_size,
        settings.asr_device,
        settings.asr_compute_type,
    )
    text = adapter.transcribe(audio_path or Path(""))
    return TranscriptionResult(text=text, provider=adapter.provider, is_demo=adapter.is_demo)

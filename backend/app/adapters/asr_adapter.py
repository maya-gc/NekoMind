"""Adaptador de ASR (transcricao de fala).

Interface unica `ASRAdapter` com implementacao mock por padrao.
O modo mock NAO baixa modelos, NAO usa rede e NAO requer chaves -
produz uma transcricao ficticia claramente marcada como demonstracao.

Para usar o faster-whisper:
  1. instale `faster-whisper` no venv do backend;
  2. ajuste NEKOMIND_ASR_PROVIDER=faster_whisper no .env;
  3. complete a classe FasterWhisperAdapter abaixo.
"""
from __future__ import annotations

from pathlib import Path

DEMO_TRANSCRIPTION = (
    "[DEMO] Transcricao simulada: expliquei o conceito de fotossintese, "
    "como as plantas convertem luz, agua e gas carbonico em glicose e "
    "oxigenio, e a diferenca entre respiracao celular e fotossintese."
)


class ASRAdapter:
    """Contrato de transcricao: recebe um arquivo de audio, retorna texto."""

    def transcribe(self, audio_path: Path) -> str:  # pragma: no cover
        raise NotImplementedError


class MockASRAdapter(ASRAdapter):
    """Implementacao de demonstracao (sem IA real)."""

    def transcribe(self, audio_path: Path) -> str:
        return DEMO_TRANSCRIPTION


class FasterWhisperAdapter(ASRAdapter):
    """Ponto de extensao para o faster-whisper (nao usado no MVP)."""

    def __init__(self, model_size: str = "small", device: str = "auto"):
        self.model_size = model_size
        self.device = device

    def transcribe(self, audio_path: Path) -> str:  # pragma: no cover
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper nao instalado no venv do backend"
            ) from exc
        model = WhisperModel(self.model_size, device=self.device)
        segments, _info = model.transcribe(str(audio_path), language="pt")
        return " ".join(seg.text.strip() for seg in segments)


def get_asr_adapter(provider: str = "mock") -> ASRAdapter:
    if provider == "faster_whisper":
        return FasterWhisperAdapter()
    return MockASRAdapter()

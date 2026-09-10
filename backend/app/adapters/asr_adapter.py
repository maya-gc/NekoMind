"""Offline demo and lazy process-wide faster-whisper lifecycle."""

from __future__ import annotations

import atexit
from pathlib import Path
from threading import RLock

# One lock also covers the lazy segment iterator and shutdown. The desktop MVP
# processes one explanation at a time; serialize all model configurations.
_model_lock = RLock()
_models: dict[tuple[str, str, str], object] = {}


def clear_asr_cache() -> None:
    """Wait for active generators, unload native resources, drop references."""
    with _model_lock:
        models = list(_models.values())
        _models.clear()
        for model in models:
            native = getattr(model, "model", None)
            if native is not None and hasattr(native, "unload_model"):
                native.unload_model()


atexit.register(clear_asr_cache)

DEMO_TRANSCRIPTION = (
    "[DEMO] Transcricao simulada: expliquei o conceito de fotossintese, "
    "como as plantas convertem luz, agua e gas carbonico em glicose e "
    "oxigenio, e a diferenca entre respiracao celular e fotossintese."
)


class ASRAdapter:
    """Contrato de transcricao: recebe um arquivo de audio, retorna texto."""

    provider = "unknown"
    is_demo = False

    def transcribe(self, audio_path: Path) -> str:  # pragma: no cover
        raise NotImplementedError


class MockASRAdapter(ASRAdapter):
    """Implementacao de demonstracao (sem IA real)."""

    provider = "mock"
    is_demo = True

    def transcribe(self, audio_path: Path) -> str:
        return DEMO_TRANSCRIPTION


class FasterWhisperAdapter(ASRAdapter):
    """Local transcription. Model path must already be available offline."""

    provider = "faster_whisper"

    def __init__(self, model_size: str = "small", device: str = "cpu", compute_type: str = "int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type

    def transcribe(self, audio_path: Path) -> str:
        if not audio_path.is_file():
            raise FileNotFoundError("Audio ausente; confira a captura e tente novamente")
        if not audio_path.stat().st_size:
            raise ValueError("Audio vazio; confira a captura e tente novamente")
        key = (self.model_size, self.device, self.compute_type)
        with _model_lock:
            if key not in _models:
                try:
                    from faster_whisper import WhisperModel
                except ImportError as exc:
                    raise RuntimeError("faster-whisper nao instalado") from exc
                # Assignment occurs only after successful initialization.
                _models[key] = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                    local_files_only=True,
                )
            model = _models[key]
            segments, _info = model.transcribe(str(audio_path), language="pt", vad_filter=True)
            return " ".join(seg.text.strip() for seg in segments).strip()


def get_asr_adapter(
    provider: str = "mock",
    model_size: str = "small",
    device: str = "cpu",
    compute_type: str = "int8",
) -> ASRAdapter:
    if provider == "faster_whisper":
        return FasterWhisperAdapter(model_size, device, compute_type)
    if provider == "mock":
        return MockASRAdapter()
    raise ValueError(f"Provedor ASR desconhecido: {provider}")

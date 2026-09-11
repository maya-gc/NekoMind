"""Small offline PCM quality checks used before pedagogical analysis."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path


def _pcm(audio_path: Path) -> bytes:
    with wave.open(str(audio_path), "rb") as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, 16000):
            raise ValueError("audio_invalid: Esperado WAV PCM16 mono 16000 Hz")
        count = wav.getnframes()
        if count <= 0:
            raise ValueError("audio_empty: Nenhum audio captado")
        pcm = wav.readframes(count)
        if len(pcm) != count * 2:
            raise ValueError("audio_invalid: WAV truncado")
    return pcm


def assess_pcm_quality(pcm: bytes) -> dict[str, float | int | bool | str]:
    if len(pcm) < 2 or len(pcm) % 2:
        raise ValueError("audio_invalid: PCM16 invalido")
    peak = 0
    clipping_count = 0
    squared = 0
    zero_crossings = 0
    previous = None
    sample_count = 0
    for (sample,) in struct.iter_unpack("<h", pcm):
        sample_count += 1
        magnitude = abs(sample)
        peak = max(peak, magnitude)
        clipping_count += int(magnitude >= 32700)
        squared += sample * sample
        if previous is not None and ((previous < 0 <= sample) or (sample < 0 <= previous)):
            zero_crossings += 1
        previous = sample
    rms = math.sqrt(squared / sample_count)
    crossing_rate = zero_crossings / max(sample_count - 1, 1)
    clipping = clipping_count >= max(3, sample_count // 1000)
    if clipping:
        quality = "clipping"
    elif rms < 10:
        quality = "low"
    elif rms > 12000 and crossing_rate > 0.30:
        quality = "noise"
    else:
        quality = "ok"
    return {
        "quality": quality,
        "level": min(100, round(peak / 32767 * 100)),
        "clipping": clipping,
        "rms": rms,
        "zero_crossing_rate": crossing_rate,
    }


def assess_audio_quality(audio_path: Path | None) -> dict[str, float | int | bool | str]:
    if audio_path is None or not audio_path.is_file():
        raise ValueError("audio_missing: Confira o microfone e tente novamente")
    try:
        pcm = _pcm(audio_path)
    except (wave.Error, EOFError, OSError) as exc:
        raise ValueError("audio_invalid: Arquivo de audio invalido") from exc
    return assess_pcm_quality(pcm)

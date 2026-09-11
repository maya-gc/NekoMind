"""Processamento de audio: junta os chunks de uma sessao em um arquivo.

MVP: os chunks PCM crus sao concatenados e encapsulados em um WAV PCM16
valido, suficiente para ASR futura e para audicao manual.
"""

from __future__ import annotations

import struct
import wave
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.models import AudioChunk
from app.services.audio_quality import assess_audio_quality


def validate_speech(audio_path: Path | None, *, detector=None) -> dict[str, float | str]:
    """WebRTC VAD mode 2; >=300ms voiced across 30ms frames, after manual finish.

    A speech classifier is imperfect, especially with distant/quiet voices or
    nonstationary noise. This gate concerns capture usability, never knowledge.
    No ratio requirement: long thinking pauses are legitimate.
    """
    if audio_path is None or not audio_path.is_file():
        raise ValueError("audio_missing: Confira o microfone e tente novamente")
    try:
        with wave.open(str(audio_path), "rb") as wav:
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, 16000):
                raise ValueError("audio_invalid: Esperado WAV PCM16 mono 16000 Hz")
            count = wav.getnframes()
            if not count:
                raise ValueError("audio_empty: Nenhum audio captado")
            if count > 16000 * 1800:
                raise ValueError("audio_invalid: Limite de 30 minutos excedido")
            pcm = wav.readframes(count)
            if len(pcm) != count * 2:
                raise ValueError("audio_invalid: WAV truncado")
    except (wave.Error, EOFError, OSError) as exc:
        raise ValueError("audio_invalid: Arquivo de audio invalido") from exc
    quality = assess_audio_quality(audio_path)
    if quality["quality"] == "clipping":
        raise ValueError("clipping: Afaste-se do microfone e tente novamente")
    if quality["quality"] == "low" and detector is None:
        raise ValueError("audio_low: Aproxime-se do microfone ou fale mais alto")
    if quality["quality"] == "noise":
        raise ValueError("audio_noise: Ruido excessivo; reduza o ruido e tente novamente")
    if detector is None:
        try:
            import webrtcvad
        except ImportError as exc:
            raise RuntimeError("vad_unavailable: Instale as dependencias do modo real") from exc
        detector = webrtcvad.Vad(2)
    frame_size = 960
    voiced = sum(
        bool(detector.is_speech(pcm[offset : offset + frame_size], 16000))
        for offset in range(0, len(pcm) - frame_size + 1, frame_size)
    )
    if voiced < 10:
        raise ValueError("no_speech: Fala insuficiente; aproxime-se do microfone e tente novamente")
    return {
        "method": "webrtcvad_mode2_30ms",
        "speech_seconds": voiced * 0.03,
        "duration_seconds": count / 16000,
    }


def merge_session_audio(db: Session, session_id: int) -> Path | None:
    """Concatena os chunks da sessao em um WAV. Retorna o caminho."""
    chunks = (
        db.query(AudioChunk)
        .filter(AudioChunk.session_id == session_id)
        .order_by(AudioChunk.sequence)
        .all()
    )
    if not chunks:
        return None

    sample_rate = chunks[0].sample_rate
    audio_format = chunks[0].format
    seen: set[int] = set()
    for expected, chunk in enumerate(chunks):
        if chunk.sequence in seen:
            raise ValueError("audio_duplicate_sequence")
        seen.add(chunk.sequence)
        if chunk.sequence != expected:
            raise ValueError("audio_sequence_gap")
        if chunk.sample_rate != sample_rate or chunk.format != audio_format:
            raise ValueError("audio_mixed_format")
        if chunk.byte_size % 2:
            raise ValueError("audio_odd_chunk_size")
        if Path(chunk.file_path).stat().st_size != chunk.byte_size:
            raise ValueError("audio_size_mismatch")
    settings = get_settings()
    out_path: Path = settings.storage_dir / f"session_{session_id}" / "session.wav"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(out_path), "wb") as wav:
        wav.setnchannels(1)  # mono
        wav.setsampwidth(2)  # 16 bits
        wav.setframerate(sample_rate)
        for chunk in chunks:
            data = Path(chunk.file_path).read_bytes()
            wav.writeframes(data)

    # Garante cabecalho consistente quando todos os chunks estavam vazios.
    if out_path.stat().st_size < struct.calcsize("<4sI4s"):
        return None
    return out_path


def estimate_duration_seconds(db: Session, session_id: int) -> float:
    """Duracao aproximada: bytes / (sample_rate * 2 bytes)."""
    chunks = db.query(AudioChunk).filter(AudioChunk.session_id == session_id).all()
    total_bytes = sum(c.byte_size for c in chunks)
    if not chunks:
        return 0.0
    rate = max(chunks[0].sample_rate, 1)
    return total_bytes / float(rate * 2)

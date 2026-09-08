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
    settings = get_settings()
    out_path: Path = settings.storage_dir / f"session_{session_id}" / "session.wav"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(out_path), "wb") as wav:
        wav.setnchannels(1)          # mono
        wav.setsampwidth(2)          # 16 bits
        wav.setframerate(sample_rate)
        for chunk in chunks:
            data = Path(chunk.file_path).read_bytes()
            # Alinha pares de bytes (PCM16) - ignora byte orfao final.
            usable = len(data) - (len(data) % 2)
            if usable:
                wav.writeframes(data[:usable])

    # Garante cabecalho consistente quando todos os chunks estavam vazios.
    if out_path.stat().st_size < struct.calcsize("<4sI4s"):
        return None
    return out_path


def estimate_duration_seconds(db: Session, session_id: int) -> float:
    """Duracao aproximada: bytes / (sample_rate * 2 bytes)."""
    chunks = (
        db.query(AudioChunk).filter(AudioChunk.session_id == session_id).all()
    )
    total_bytes = sum(c.byte_size for c in chunks)
    if not chunks:
        return 0.0
    rate = max(chunks[0].sample_rate, 1)
    return total_bytes / float(rate * 2)

"""Ingestao de audio: grava chunks recebidos e registra metadados."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.models import AudioChunk, StudySession


def save_chunk(
    db: Session,
    session: StudySession,
    data: bytes,
    sequence: int,
    audio_format: str = "pcm_s16le",
    sample_rate: int = 16000,
) -> AudioChunk:
    """Grava o chunk em disco e persiste os metadados no banco."""
    settings = get_settings()
    session_dir: Path = settings.storage_dir / f"session_{session.id}"
    session_dir.mkdir(parents=True, exist_ok=True)

    file_path = session_dir / f"chunk_{sequence:05d}.raw"
    file_path.write_bytes(data)

    chunk = AudioChunk(
        session_id=session.id,
        sequence=sequence,
        format=audio_format,
        sample_rate=sample_rate,
        byte_size=len(data),
        file_path=str(file_path),
    )
    db.add(chunk)
    db.commit()
    db.refresh(chunk)
    return chunk

"""Ingestao de audio: grava chunks recebidos e registra metadados."""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.models import AudioChunk, SessionStatus, StudySession

logger = logging.getLogger(__name__)


class AudioConflictError(ValueError):
    """Raised when a retransmitted chunk does not match the original."""


def save_chunk(
    db: Session,
    session: StudySession,
    data: bytes,
    sequence: int,
    audio_format: str = "pcm_s16le",
    sample_rate: int = 16000,
) -> tuple[AudioChunk, bool]:
    """Grava o chunk em disco e persiste os metadados no banco."""
    db.connection().execute(text("BEGIN IMMEDIATE"))
    db.refresh(session)
    if session.status not in {SessionStatus.recording, SessionStatus.paused}:
        db.rollback()
        raise AudioConflictError("Sessao nao aceita audio neste estado")
    existing = (
        db.query(AudioChunk)
        .filter(AudioChunk.session_id == session.id, AudioChunk.sequence == sequence)
        .first()
    )
    if existing is not None:
        try:
            existing_data = Path(existing.file_path).read_bytes()
        except OSError as exc:
            db.rollback()
            raise AudioConflictError("Chunk registrado sem arquivo de audio") from exc
        if (
            existing_data == data
            and existing.format == audio_format
            and existing.sample_rate == sample_rate
        ):
            db.commit()
            return existing, True
        db.rollback()
        raise AudioConflictError("Chunk ja recebido com conteudo diferente")
    if sequence > 0:
        previous = (
            db.query(AudioChunk)
            .filter(AudioChunk.session_id == session.id, AudioChunk.sequence == sequence - 1)
            .first()
        )
        if previous is None:
            db.rollback()
            raise AudioConflictError("Sequencia de audio com lacuna")

    settings = get_settings()
    session_dir: Path = settings.storage_dir / f"session_{session.id}"
    session_dir.mkdir(parents=True, exist_ok=True)

    file_path = session_dir / f"chunk_{sequence:05d}_{uuid4().hex}.raw"
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
    committed = False
    try:
        db.flush()
        db.commit()
        committed = True
        try:
            db.refresh(chunk)
        except SQLAlchemyError:
            logger.warning("Chunk persistido; falha ao atualizar a instancia local.")
        return chunk, False
    except IntegrityError:
        db.rollback()
        if not committed:
            file_path.unlink(missing_ok=True)
        existing = (
            db.query(AudioChunk)
            .filter(AudioChunk.session_id == session.id, AudioChunk.sequence == sequence)
            .first()
        )
        if existing is not None:
            existing_data = Path(existing.file_path).read_bytes()
            if (
                existing_data == data
                and existing.format == audio_format
                and existing.sample_rate == sample_rate
            ):
                return existing, True
        raise AudioConflictError("Chunk ja recebido com conteudo diferente")
    except Exception:
        db.rollback()
        if not committed:
            file_path.unlink(missing_ok=True)
        raise

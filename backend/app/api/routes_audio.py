"""Recepcao de chunks de audio de uma sessao."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import AudioChunk
from app.repositories.session_repository import SessionRepository
from app.services import audio_ingestion

router = APIRouter(prefix="/api/v1", tags=["audio"])


@router.post("/sessions/{session_id}/audio", status_code=201)
def upload_audio_chunk(
    session_id: int,
    file: UploadFile = File(...),
    sequence: int = Form(...),
    audio_format: str = Form(default="pcm_s16le"),
    sample_rate: int = Form(default=16000),
    db: Session = Depends(get_db),
) -> dict:
    """Recebe um chunk de audio (multipart) e o persiste em disco + banco."""
    session = SessionRepository(db).get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada")

    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Chunk vazio")

    chunk: AudioChunk = audio_ingestion.save_chunk(
        db,
        session,
        data=data,
        sequence=sequence,
        audio_format=audio_format,
        sample_rate=sample_rate,
    )
    return {
        "chunk_id": chunk.id,
        "session_id": session_id,
        "sequence": chunk.sequence,
        "byte_size": chunk.byte_size,
    }

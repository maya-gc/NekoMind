"""Recepcao de chunks de audio de uma sessao."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import SessionStatus
from app.repositories.session_repository import SessionRepository
from app.services import audio_ingestion

router = APIRouter(prefix="/api/v1", tags=["audio"])
MAX_CHUNK_BYTES = 16000 * 2 * 30


@router.post("/sessions/{session_id}/audio", status_code=201)
def upload_audio_chunk(
    session_id: int,
    response: Response,
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
    if session.status not in {SessionStatus.recording, SessionStatus.paused}:
        raise HTTPException(status_code=409, detail="Sessao nao aceita audio neste estado")
    if audio_format != "pcm_s16le" or sample_rate != 16000:
        raise HTTPException(status_code=422, detail="Audio deve ser PCM16 mono 16 kHz")
    if sequence < 0:
        raise HTTPException(status_code=422, detail="Sequencia invalida")

    data = file.file.read(MAX_CHUNK_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="Chunk vazio")
    if len(data) > MAX_CHUNK_BYTES:
        raise HTTPException(status_code=413, detail="Chunk excede 30 segundos")
    if len(data) % 2:
        raise HTTPException(status_code=422, detail="Chunk PCM16 truncado")

    try:
        chunk, deduplicated = audio_ingestion.save_chunk(
            db,
            session,
            data=data,
            sequence=sequence,
            audio_format=audio_format,
            sample_rate=sample_rate,
        )
    except audio_ingestion.AudioConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if deduplicated:
        response.status_code = 200
    return {
        "chunk_id": chunk.id,
        "session_id": session_id,
        "sequence": chunk.sequence,
        "byte_size": chunk.byte_size,
        "deduplicated": deduplicated,
    }

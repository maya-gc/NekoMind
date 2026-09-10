"""Rotas das sessoes de estudo e do resumo do dashboard."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import SessionStatus, StudySession
from app.repositories.session_repository import SessionRepository
from app.repositories.topic_repository import TopicRepository
from app.schemas.metrics import DashboardSummary
from app.schemas.session import (
    CaptureStateUpdate,
    SessionCreate,
    SessionDetail,
    SessionFinish,
    SessionOut,
)
from app.services import session_analysis

router = APIRouter(prefix="/api/v1", tags=["sessions"])


@router.post("/sessions", response_model=SessionOut, status_code=201)
def create_session(payload: SessionCreate, db: Session = Depends(get_db)):
    """Inicia uma nova sessao de estudo."""
    repo = SessionRepository(db)
    if payload.request_id:
        existing = repo.get_by_start_request_id(payload.request_id)
        if existing is not None and _start_conflicts(existing, payload):
            raise HTTPException(
                status_code=409,
                detail="request_id ja usado com outro payload",
            )
        if existing is not None:
            return existing
    session = repo.create(
        title=payload.title,
        request_id=payload.request_id,
        capture_source=payload.capture_source,
        device_session_id=payload.device_session_id,
    )
    if payload.request_id and _start_conflicts(session, payload):
        raise HTTPException(status_code=409, detail="request_id ja usado com outro payload")
    return session


def _start_conflicts(session: StudySession, payload: SessionCreate) -> bool:
    return any(
        (
            session.title != payload.title,
            session.capture_source != payload.capture_source,
            session.device_session_id != payload.device_session_id,
        )
    )


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    return SessionRepository(db).list(limit=limit, offset=offset)


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def get_session(session_id: int, db: Session = Depends(get_db)):
    session = SessionRepository(db).get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada")
    return session


@router.post("/sessions/{session_id}/capture-state", response_model=SessionOut)
def update_capture_state(
    session_id: int,
    payload: CaptureStateUpdate,
    db: Session = Depends(get_db),
):
    repo = SessionRepository(db)
    values: dict[str, object] = {"status": SessionStatus(payload.state)}
    if payload.state == "error":
        values.update(
            {
                "error_code": payload.error_code or "capture_error",
                "error_message": payload.error_message or "Falha na captura de audio.",
                "ended_at": datetime.now(UTC),
            }
        )
    else:
        values.update({"error_code": None, "error_message": None})
    db.query(StudySession).filter(
        StudySession.id == session_id,
        StudySession.status.in_([SessionStatus.recording, SessionStatus.paused]),
    ).update(values, synchronize_session=False)
    db.commit()
    db.expire_all()
    session = repo.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada")
    return session


@router.post("/sessions/{session_id}/finish", response_model=SessionDetail)
def finish_session(
    session_id: int,
    payload: SessionFinish | None = None,
    db: Session = Depends(get_db),
):
    """Finaliza a sessao e dispara a analise (transcricao, topicos, metricas)."""
    repo = SessionRepository(db)
    session = repo.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada")
    try:
        session = session_analysis.analyze_session(
            db, session, finish_request_id=payload.request_id if payload else None
        )
    except session_analysis.AnalysisRejectedError as exc:
        current = repo.get(session_id)
        if current is None:
            raise HTTPException(status_code=404, detail="Sessao nao encontrada") from exc
        return JSONResponse(
            status_code=422,
            content=SessionDetail.model_validate(current).model_dump(mode="json"),
        )
    except Exception as exc:
        current = repo.get(session_id)
        if current is None:
            raise HTTPException(status_code=404, detail="Sessao nao encontrada") from exc
        return JSONResponse(
            status_code=500,
            content=SessionDetail.model_validate(current).model_dump(mode="json"),
        )
    return repo.get(session.id)


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db)):
    """Resumo agregado para o dashboard do frontend."""
    total_sessions = db.query(func.count(StudySession.id)).scalar() or 0
    total_seconds = db.query(func.coalesce(func.sum(StudySession.duration_seconds), 0.0)).scalar()
    avg_clarity = (
        db.query(func.avg(StudySession.clarity_score))
        .filter(StudySession.clarity_score.isnot(None))
        .scalar()
    )
    top_topics = TopicRepository(db).most_frequent(limit=5)
    return DashboardSummary(
        total_sessions=int(total_sessions),
        total_study_seconds=float(total_seconds or 0.0),
        avg_clarity_score=round(float(avg_clarity), 2) if avg_clarity else None,
        top_topics=[(name, int(n)) for name, n in top_topics],
    )

"""Rotas das sessoes de estudo e do resumo do dashboard."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import StudySession
from app.repositories.session_repository import SessionRepository
from app.repositories.topic_repository import TopicRepository
from app.schemas.metrics import DashboardSummary
from app.schemas.session import SessionCreate, SessionDetail, SessionOut
from app.services import session_analysis

router = APIRouter(prefix="/api/v1", tags=["sessions"])


@router.post("/sessions", response_model=SessionOut, status_code=201)
def create_session(payload: SessionCreate, db: Session = Depends(get_db)):
    """Inicia uma nova sessao de estudo."""
    return SessionRepository(db).create(title=payload.title)


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(
    limit: int = 100, offset: int = 0, db: Session = Depends(get_db)
):
    return SessionRepository(db).list(limit=limit, offset=offset)


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def get_session(session_id: int, db: Session = Depends(get_db)):
    session = SessionRepository(db).get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada")
    return session


@router.post("/sessions/{session_id}/finish", response_model=SessionDetail)
def finish_session(session_id: int, db: Session = Depends(get_db)):
    """Finaliza a sessao e dispara a analise (transcricao, topicos, metricas)."""
    repo = SessionRepository(db)
    session = repo.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada")
    session = session_analysis.analyze_session(db, session)
    return repo.get(session.id)


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db)):
    """Resumo agregado para o dashboard do frontend."""
    total_sessions = db.query(func.count(StudySession.id)).scalar() or 0
    total_seconds = (
        db.query(func.coalesce(func.sum(StudySession.duration_seconds), 0.0)).scalar()
    )
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

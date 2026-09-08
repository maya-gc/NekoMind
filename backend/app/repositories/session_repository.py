"""Acesso a dados das sessoes de estudo."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.models import StudySession


class SessionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, title: str | None = None) -> StudySession:
        session = StudySession(title=title)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get(self, session_id: int) -> StudySession | None:
        stmt = (
            select(StudySession)
            .where(StudySession.id == session_id)
            .options(
                selectinload(StudySession.topics),
                selectinload(StudySession.metrics),
            )
        )
        return self.db.scalars(stmt).first()

    def list(self, limit: int = 100, offset: int = 0) -> list[StudySession]:
        stmt = (
            select(StudySession)
            .order_by(StudySession.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt).all())

    def save(self, session: StudySession) -> StudySession:
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

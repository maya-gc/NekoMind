"""Acesso a dados das sessoes de estudo."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.database.models import SessionStatus, StudySession


class SessionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        title: str | None = None,
        *,
        request_id: str | None = None,
        capture_source: str | None = None,
        device_session_id: str | None = None,
    ) -> StudySession:
        if request_id:
            existing = self.get_by_start_request_id(request_id)
            if existing is not None:
                return existing
        settings = get_settings()
        mode = settings.mode
        session = StudySession(
            title=title,
            request_id=request_id,
            start_request_id=request_id,
            capture_source=capture_source,
            device_session_id=device_session_id,
            asr_provider_config=settings.asr_provider,
            topic_provider_config=settings.llm_provider,
            mode=mode,
            is_demo=mode != "real",
        )
        self.db.add(session)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            if request_id:
                existing = self.get_by_start_request_id(request_id)
                if existing is not None:
                    return existing
            raise
        self.db.refresh(session)
        return session

    def get_by_start_request_id(self, request_id: str) -> StudySession | None:
        stmt = (
            select(StudySession)
            .where(StudySession.start_request_id == request_id)
            .options(
                selectinload(StudySession.topics),
                selectinload(StudySession.metrics),
            )
        )
        return self.db.scalars(stmt).first()

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

    def claim_processing(
        self,
        session_id: int,
        finish_request_id: str | None = None,
    ) -> StudySession | None:
        values: dict[str, object] = {
            "status": SessionStatus.processing,
            "error_code": None,
            "error_message": None,
        }
        if finish_request_id:
            values["finish_request_id"] = finish_request_id
        claimed = (
            self.db.query(StudySession)
            .filter(
                StudySession.id == session_id,
                StudySession.status.in_([SessionStatus.recording, SessionStatus.paused]),
            )
            .update(values, synchronize_session=False)
        )
        self.db.commit()
        self.db.expire_all()
        if claimed != 1:
            return None
        return self.get(session_id)

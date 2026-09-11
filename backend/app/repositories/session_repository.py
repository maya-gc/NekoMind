"""Acesso a dados das sessoes de estudo."""

from __future__ import annotations

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.database.models import DeletedSessionTombstone, SessionStatus, StudySession


class TombstonedSessionRequestError(ValueError):
    """Raised when a replayed start_request_id belongs to a deleted session."""


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
        if self.db.get_bind().dialect.name == "sqlite":
            # Reserve the writer before selecting a new identity. Separate
            # requests/processes must not both allocate the same MAX(id)+1.
            self.db.execute(text("BEGIN IMMEDIATE"))
        if request_id:
            existing = self.get_by_start_request_id(request_id)
            if existing is not None:
                return existing
            if self.is_tombstoned_start_request_id(request_id):
                raise TombstonedSessionRequestError("start_request_id pertence a sessao excluida")
        settings = get_settings()
        mode = settings.mode
        session = StudySession(
            id=self.next_session_id(),
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
                if self.is_tombstoned_start_request_id(request_id):
                    raise TombstonedSessionRequestError(
                        "start_request_id pertence a sessao excluida"
                    )
            raise
        self.db.refresh(session)
        return session

    def next_session_id(self) -> int:
        max_live = self.db.query(func.coalesce(func.max(StudySession.id), 0)).scalar() or 0
        max_deleted = (
            self.db.query(func.coalesce(func.max(DeletedSessionTombstone.session_id), 0)).scalar()
            or 0
        )
        return int(max(max_live, max_deleted)) + 1

    def is_tombstoned_start_request_id(self, request_id: str) -> bool:
        stmt = select(DeletedSessionTombstone.session_id).where(
            DeletedSessionTombstone.start_request_id == request_id
        )
        return self.db.execute(stmt).first() is not None

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
        from_statuses: set[SessionStatus] | None = None,
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
                StudySession.status.in_(
                    from_statuses or {SessionStatus.recording, SessionStatus.paused}
                ),
                StudySession.deletion_pending.is_(False),
            )
            .update(values, synchronize_session=False)
        )
        self.db.commit()
        self.db.expire_all()
        if claimed != 1:
            return None
        return self.get(session_id)

    def claim_deletion(
        self,
        session_id: int,
        *,
        allowed_statuses: set[SessionStatus],
    ) -> StudySession | None:
        claimed = (
            self.db.query(StudySession)
            .filter(
                StudySession.id == session_id,
                StudySession.status.in_(allowed_statuses),
                StudySession.deletion_pending.is_(False),
            )
            .update({"deletion_pending": True}, synchronize_session=False)
        )
        self.db.commit()
        self.db.expire_all()
        if claimed != 1:
            return None
        return self.get(session_id)

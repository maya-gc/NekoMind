"""Acesso a dados dos topicos extraidos."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Topic


class TopicRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_many(self, session_id: int, topics: list[dict]) -> list[Topic]:
        rows = [
            Topic(
                session_id=session_id,
                name=t["name"],
                relevance=float(t.get("relevance", 1.0)),
                notes=t.get("notes"),
            )
            for t in topics
        ]
        self.db.add_all(rows)
        return rows

    def replace_many(self, session_id: int, topics: list[dict]) -> list[Topic]:
        self.db.query(Topic).filter(Topic.session_id == session_id).delete()
        self.db.flush()
        return self.create_many(session_id, topics)

    def most_frequent(self, limit: int = 5) -> list[tuple[str, int]]:
        stmt = (
            select(Topic.name, func.count(Topic.id).label("n"))
            .group_by(Topic.name)
            .order_by(func.count(Topic.id).desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).all())

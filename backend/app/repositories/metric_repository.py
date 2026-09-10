"""Acesso a dados das metricas de sessao."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.database.models import Metric


class MetricRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_many(
        self, session_id: int, metrics: dict[str, tuple[float, str | None]]
    ) -> list[Metric]:
        rows = [
            Metric(session_id=session_id, name=name, value=value, unit=unit)
            for name, (value, unit) in metrics.items()
        ]
        self.db.add_all(rows)
        return rows

    def replace_many(
        self, session_id: int, metrics: dict[str, tuple[float, str | None]]
    ) -> list[Metric]:
        self.db.query(Metric).filter(Metric.session_id == session_id).delete()
        self.db.flush()
        return self.create_many(session_id, metrics)

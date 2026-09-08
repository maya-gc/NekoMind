"""Schemas Pydantic das sessoes de estudo."""
from __future__ import annotations

import enum
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.metrics import MetricOut
from app.schemas.topic import TopicOut


class SessionCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: float
    status: str
    transcription: str | None
    clarity_score: float | None
    is_demo: bool

    @field_validator("status", mode="before")
    @classmethod
    def _coerce_status(cls, value: object) -> str:
        """Converte o enum SessionStatus para o valor string serializavel."""
        if isinstance(value, enum.Enum):
            return str(value.value)
        return str(value)


class SessionDetail(SessionOut):
    topics: list[TopicOut] = []
    metrics: list[MetricOut] = []

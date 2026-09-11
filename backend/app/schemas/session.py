"""Schemas Pydantic das sessoes de estudo."""

from __future__ import annotations

import enum
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.metrics import MetricOut
from app.schemas.topic import TopicOut


class SessionCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    request_id: str | None = Field(default=None, max_length=100)
    capture_source: str | None = Field(default=None, max_length=80)
    device_session_id: str | None = Field(default=None, max_length=100)


class SessionFinish(BaseModel):
    request_id: str | None = Field(default=None, max_length=100)


class CaptureStateUpdate(BaseModel):
    request_id: str | None = Field(default=None, max_length=100)
    state: str = Field(pattern="^(recording|paused|error)$")
    error_code: str | None = Field(default=None, max_length=80)
    error_message: str | None = Field(default=None, max_length=240)


class SessionRecover(BaseModel):
    action: str = Field(pattern="^(resume|analyze|discard)$")
    request_id: str | None = Field(default=None, max_length=100)


class SessionDelete(BaseModel):
    confirmed: bool = False


class SessionCancel(BaseModel):
    confirmed: bool = False
    request_id: str | None = Field(default=None, max_length=100)


class SessionSubjectUpdate(BaseModel):
    subject: str | None = Field(default=None, max_length=200)
    confirmed: bool = False


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
    start_request_id: str | None = None
    finish_request_id: str | None = None
    device_session_id: str | None = None
    capture_source: str | None = None
    asr_provider_used: str | None = None
    topic_provider_used: str | None = None
    analysis_origin: str | None = None
    audio_validation: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    mode: str = "demo"
    request_id: str | None = None
    speech_validation: str | None = None
    subject: str | None = None
    subject_confirmed: bool = False
    metric_method_version: str = "heuristic-v1"
    journey: dict = Field(default_factory=dict)
    deletion_pending: bool = False

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

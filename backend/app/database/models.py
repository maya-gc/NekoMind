"""Modelos SQLAlchemy do NekoMind.

Entidades: StudySession, Topic, Metric, AudioChunk.
Ver docs/data_model.md para o DER e justificativas.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(UTC)


class SessionStatus(str, enum.Enum):
    recording = "recording"  # recebendo audio
    paused = "paused"  # captura pausada pelo touch
    processing = "processing"  # transcricao/analise em andamento
    completed = "completed"  # analise concluida
    error = "error"  # falha em alguma etapa


class StudySession(Base):
    __tablename__ = "study_sessions"
    __table_args__ = (
        UniqueConstraint("start_request_id", name="uq_study_sessions_start_request_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus), default=SessionStatus.recording
    )
    transcription: Mapped[str | None] = mapped_column(Text, nullable=True)
    clarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_demo: Mapped[bool] = mapped_column(default=False)
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    start_request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    finish_request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    device_session_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    capture_source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    asr_provider_config: Mapped[str | None] = mapped_column(String(80), nullable=True)
    topic_provider_config: Mapped[str | None] = mapped_column(String(80), nullable=True)
    asr_provider_used: Mapped[str | None] = mapped_column(String(80), nullable=True)
    topic_provider_used: Mapped[str | None] = mapped_column(String(80), nullable=True)
    analysis_origin: Mapped[str | None] = mapped_column(String(80), nullable=True)
    speech_validation: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_validation: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    mode: Mapped[str] = mapped_column(String(16), default="demo")

    topics: Mapped[list[Topic]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    metrics: Mapped[list[Metric]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    audio_chunks: Mapped[list[AudioChunk]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("study_sessions.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    relevance: Mapped[float] = mapped_column(Float, default=1.0)  # 0..1
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    session: Mapped[StudySession] = relationship(back_populates="topics")


class Metric(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("study_sessions.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))  # ex.: "word_count"
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)

    session: Mapped[StudySession] = relationship(back_populates="metrics")


class AudioChunk(Base):
    __tablename__ = "audio_chunks"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence", name="uq_audio_chunks_session_sequence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("study_sessions.id", ondelete="CASCADE"))
    sequence: Mapped[int] = mapped_column(Integer)
    format: Mapped[str] = mapped_column(String(32), default="pcm_s16le")
    sample_rate: Mapped[int] = mapped_column(Integer, default=16000)
    byte_size: Mapped[int] = mapped_column(Integer)
    file_path: Mapped[str] = mapped_column(String(500))

    session: Mapped[StudySession] = relationship(back_populates="audio_chunks")

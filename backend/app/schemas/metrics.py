"""Schemas Pydantic de metricas e do resumo do dashboard."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class MetricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    name: str
    value: float
    unit: str | None


class AudioChunkIn(BaseModel):
    """Metadados de um chunk enviado pelo dispositivo ou cliente."""

    sequence: int
    format: str = "pcm_s16le"
    sample_rate: int = 16000


class DashboardSummary(BaseModel):
    total_sessions: int
    total_study_seconds: float
    avg_clarity_score: float | None
    top_topics: list[tuple[str, int]]

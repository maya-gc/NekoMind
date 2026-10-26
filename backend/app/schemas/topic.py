"""Schemas Pydantic de topicos extraidos."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class TopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    name: str
    relevance: float
    notes: str | None

"""Servico de extracao de topicos a partir da transcricao (LLM)."""
from __future__ import annotations

from app.adapters.llm_adapter import get_llm_adapter
from app.config import get_settings


def extract_topics(transcription: str) -> list[dict]:
    """Retorna lista de topicos: {name, relevance, notes}."""
    settings = get_settings()
    adapter = get_llm_adapter(settings.llm_provider, settings.llm_api_key)
    return adapter.extract_topics(transcription)

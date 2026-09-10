"""Servico de extracao de topicos a partir da transcricao validada."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from app.adapters.llm_adapter import _normalize, get_llm_adapter
from app.config import get_settings


@dataclass(frozen=True)
class TopicExtractionResult:
    topics: list[dict]
    provider: str
    is_demo: bool


def extract_topics(transcription: str) -> list[dict]:
    """Retorna lista de topicos: {name, relevance, notes}."""
    return extract_topics_result(transcription).topics


def extract_topics_result(
    transcription: str,
    *,
    provider: str | None = None,
) -> TopicExtractionResult:
    """Return validated topics and the effective provider."""
    settings = get_settings()
    adapter = get_llm_adapter(provider or settings.llm_provider, settings.llm_api_key)
    if (
        not isinstance(transcription, str)
        or not transcription.strip()
        or len(transcription) > 100000
    ):
        raise ValueError("Transcricao vazia ou invalida")
    topics = _validate_topics(
        adapter.extract_topics(transcription), transcription, is_demo=adapter.is_demo
    )
    return TopicExtractionResult(
        topics=topics,
        provider=adapter.provider,
        is_demo=adapter.is_demo,
    )


def _validate_topics(topics: object, transcription: str, *, is_demo: bool = False) -> list[dict]:
    if not isinstance(topics, list) or len(topics) > 8:
        raise ValueError("Extrator retornou lista invalida")
    normalized_text = " ".join(_normalize(transcription).split())
    valid, seen = [], set()
    for raw in topics:
        if not isinstance(raw, dict):
            raise TypeError("Topico deve ser objeto")
        name = raw.get("name")
        if not isinstance(name, str) or not name.strip() or len(name) > 200:
            raise ValueError("Nome de topico invalido")
        name = name.strip()
        relevance = raw.get("relevance")
        if (
            type(relevance) not in {int, float}
            or not math.isfinite(relevance)
            or not 0 <= relevance <= 1
        ):
            raise ValueError("Relevancia invalida")
        notes = raw.get("notes")
        if notes is not None and (not isinstance(notes, str) or len(notes) > 1000):
            raise ValueError("Notas invalidas")
        normalized = " ".join(_normalize(name).split())
        if normalized in seen:
            raise ValueError("Topico duplicado")
        if not is_demo and not re.search(
            r"(?<!\w)" + re.escape(normalized) + r"(?!\w)", normalized_text
        ):
            raise ValueError("Topico nao encontrado na transcricao")
        seen.add(normalized)
        valid.append({"name": name, "relevance": float(relevance), "notes": notes})
    return valid

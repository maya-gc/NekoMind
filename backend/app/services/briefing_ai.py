"""Choose grounded briefing points with a local Ollama model; never use a cloud fallback."""

from __future__ import annotations

import json

import httpx

from app.services.content_matching import suggest_review_points

MAX_AI_CHARS = 12_000
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"


class BriefingAIError(ValueError):
    pass


def analyze_briefing(text: str, model: str) -> dict:
    source = text.strip()
    if not source:
        raise BriefingAIError("Cole ou importe um texto antes de analisar.")
    if len(source) > MAX_AI_CHARS:
        raise BriefingAIError(
            "Para a análise com IA, use até 12 mil caracteres ou selecione um trecho menor."
        )
    candidates = suggest_review_points(source, limit=80)
    if not candidates:
        raise BriefingAIError("O texto precisa conter ao menos uma frase legível.")
    numbered = "\n".join(f"{index}: {point}" for index, point in enumerate(candidates))
    prompt = (
        "Você prepara um briefing em português. Escolha de 1 a 8 índices das frases "
        "mais úteis para acompanhar uma explicação oral. Use somente índices da lista. "
        "Não acrescente fatos, não reescreva frases, não avalie domínio ou correção. "
        'Responda SOMENTE JSON no formato {"indices":[0,1]}.\n\n'
        f"Frases do material:\n{numbered}"
    )
    try:
        with httpx.Client(trust_env=False, timeout=45) as client:
            response = client.post(
                OLLAMA_URL,
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0, "num_predict": 256},
                },
            )
        response.raise_for_status()
        result = response.json()
        selected = json.loads(result["response"])["indices"]
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise BriefingAIError(
            "A IA local não respondeu corretamente. Confira se o Ollama e o modelo estão ativos."
        ) from exc
    if (
        not isinstance(selected, list)
        or not 1 <= len(selected) <= 8
        or any(type(index) is not int or not 0 <= index < len(candidates) for index in selected)
        or len(set(selected)) != len(selected)
    ):
        raise BriefingAIError(
            "A IA local devolveu pontos inválidos. Revise o texto e tente novamente."
        )
    return {
        "text": source,
        "points": [candidates[index] for index in selected],
        "provider": "ollama_local",
        "model": model,
    }

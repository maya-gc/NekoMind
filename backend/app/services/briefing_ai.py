"""Choose grounded briefing points with a local Ollama model; never use a cloud fallback."""

from __future__ import annotations

import json
import re

import httpx

from app.services.content_matching import suggest_review_points

CHUNK_CHARS = 6_000
MAX_POINTS = 20
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"


class BriefingAIError(ValueError):
    pass


def analyze_briefing(text: str, model: str) -> dict:
    source = text.strip()
    if not source:
        raise BriefingAIError("Cole ou importe um texto antes de analisar.")
    # Keep the complete source for review and persistence. Analyze every
    # eligible sentence in bounded chunks; do not discard the document tail.
    available = suggest_review_points(source, limit=10_000)
    prose = [
        sentence for sentence in available
        if re.match(r"^[A-ZÀ-Þ]", sentence)
        and sentence.endswith((".", "!", "?"))
        and not sentence.endswith("..")
        and len(re.findall(r"[A-Za-zÀ-ÿ]{2,}", sentence)) >= 3
        and sum(char.isalpha() for char in sentence) / len(sentence) >= 0.65
        and "\\displaystyle" not in sentence
    ]
    if prose:
        available = prose
    chunks: list[list[str]] = []
    current: list[str] = []
    current_chars = 0
    current_region = 0
    for sentence in available:
        position = source.find(sentence)
        region = max(position, 0) // CHUNK_CHARS
        if current and (region != current_region or current_chars + len(sentence) > CHUNK_CHARS):
            chunks.append(current)
            current, current_chars = [], 0
        current_region = region
        current.append(sentence)
        current_chars += len(sentence)
    if current:
        chunks.append(current)
    if not chunks:
        raise BriefingAIError("O texto precisa conter ao menos uma frase legível.")
    points: list[str] = []
    try:
        with httpx.Client(trust_env=False, timeout=45) as client:
            for candidates in chunks:
                numbered = "\n".join(f"{index}: {point}" for index, point in enumerate(candidates))
                prompt = (
                    "Você prepara um briefing em português. Escolha de 1 a 3 índices das "
                    "frases mais úteis desta parte do material. Prefira frases completas, "
                    "independentes e com conceitos diferentes. Evite nomes soltos, títulos, "
                    "fórmulas e trechos sem contexto. Use somente índices da lista. "
                    "Não acrescente fatos, não reescreva frases, não avalie domínio ou correção. "
                    'Responda SOMENTE JSON no formato {"indices":[0,1]}.\n\n'
                    f"Frases do material:\n{numbered}"
                )
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
                selected = json.loads(response.json()["response"])["indices"]
                if (
                    not isinstance(selected, list)
                    or not 1 <= len(selected) <= 3
                    or any(type(index) is not int or not 0 <= index < len(candidates) for index in selected)
                    or len(set(selected)) != len(selected)
                ):
                    raise BriefingAIError(
                        "A IA local devolveu pontos inválidos. Revise o texto e tente novamente."
                    )
                points.extend(candidates[index] for index in selected)
    except BriefingAIError:
        raise
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise BriefingAIError(
            "A IA local não respondeu corretamente. Confira se o Ollama e o modelo estão ativos."
        ) from exc
    unique = list(dict.fromkeys(points))
    if len(unique) > MAX_POINTS:
        unique = [unique[round(i * (len(unique) - 1) / (MAX_POINTS - 1))] for i in range(MAX_POINTS)]
    return {
        "text": source,
        "points": unique,
        "provider": "ollama_local",
        "model": model,
        "sampled": len(chunks) > 1,
        "sections_analyzed": len(chunks),
    }

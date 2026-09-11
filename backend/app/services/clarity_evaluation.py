"""Metricas heuristicas de clareza e abrangencia.

ATENCAO: estas metricas sao HEURISTICAS DE DEMONSTRACAO, pensadas para
apoio a reflexao do estudante - nao sao avaliacao pedagogica.
Cada funcao e simples, explicavel e documentada.
"""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"\b\w+\b", flags=re.UNICODE)


def word_count(text: str) -> int:
    """Numero total de palavras da transcricao."""
    return len(_WORD_RE.findall(text or ""))


def lexical_diversity(text: str) -> float:
    """Diversidade lexical simples: palavras unicas / total (0..1).

    Valores muito baixos sugerem repeticao excessiva; muito altos podem
    indicar texto curto demais. Interpretar com cautela.
    """
    words = [w.lower() for w in _WORD_RE.findall(text or "")]
    if not words:
        return 0.0
    return round(len(set(words)) / len(words), 3)


def topic_coverage(topic_count: int, target: int = 5) -> float:
    """Cobertura estimada de topicos: min(topic_count / target, 1).

    Heuristica simples: assume que cobrir ~5 topicos relevantes equivale
    a uma explicacao abrangente do tema.
    """
    if target <= 0:
        return 0.0
    return round(min(topic_count / target, 1.0), 3)


def clarity_score(text: str, duration_seconds: float, topic_count: int) -> float:
    """Pontuacao de clareza de DEMONSTRACAO (0..10).

    Componentes (pesos arbitrarios, documentados):
      - diversidade lexical (40%): vocabulario variado;
      - ritmo de fala 80..180 palavras/min (30%): penaliza muito lento
        ou muito acelerado;
      - presenca de topicos (30%): ao menos 3 topicos pontua o maximo.
    """
    diversity = lexical_diversity(text)
    words = word_count(text)
    wpm = (words / duration_seconds * 60) if duration_seconds > 0 else 0.0

    if wpm <= 0:
        pace = 0.0
    elif wpm < 80:
        pace = wpm / 80
    elif wpm <= 180:
        pace = 1.0
    else:
        pace = max(0.0, 1.0 - (wpm - 180) / 180)

    topics = min(topic_count / 3, 1.0)

    score = 10.0 * (0.4 * diversity + 0.3 * pace + 0.3 * topics)
    return round(score, 2)

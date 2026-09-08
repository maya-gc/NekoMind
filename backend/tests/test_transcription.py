"""Testes dos adapters de transcricao e das heuristicas."""
from __future__ import annotations

from pathlib import Path

from app.adapters.asr_adapter import MockASRAdapter
from app.adapters.llm_adapter import MockLLMAdapter
from app.services import clarity_evaluation


def test_mock_asr_marca_demonstracao() -> None:
    text = MockASRAdapter().transcribe(Path("inexistente.raw"))
    assert "[DEMO]" in text


def test_mock_llm_extrai_topicos_demo() -> None:
    topics = MockLLMAdapter().extract_topics("qualquer texto")
    assert len(topics) >= 1
    assert all("name" in t and "relevance" in t for t in topics)


def test_heuristicas_basicas() -> None:
    text = "gato gato gato cao"
    assert clarity_evaluation.word_count(text) == 4
    # 2 palavras unicas / 4 totais
    assert clarity_evaluation.lexical_diversity(text) == 0.5
    assert clarity_evaluation.topic_coverage(10) == 1.0
    score = clarity_evaluation.clarity_score(text, 60.0, 3)
    assert 0.0 <= score <= 10.0

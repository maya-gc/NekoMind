"""Topic extraction must be grounded in the actual transcript."""

from __future__ import annotations

import pytest

from app.adapters.llm_adapter import get_llm_adapter
from app.services.topic_extraction import extract_topics_result


def test_local_topics_follow_different_transcripts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEKOMIND_LLM_PROVIDER", "local_keywords")

    plants = extract_topics_result(
        "Fotossintese nas plantas usa luz, agua e gas carbonico para formar glicose."
    )
    calculus = extract_topics_result(
        "Derivada, limite e taxa de variacao explicam o comportamento de uma funcao."
    )

    plant_names = {topic["name"] for topic in plants.topics}
    calculus_names = {topic["name"] for topic in calculus.topics}

    assert plants.provider == "local_keywords"
    assert plants.is_demo is False
    assert any("fotossintese" in name or "plantas" in name for name in plant_names)
    assert any("derivada" in name or "limite" in name for name in calculus_names)
    assert plant_names.isdisjoint(calculus_names)


def test_local_topics_do_not_pad_or_invent_when_text_is_too_short(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NEKOMIND_LLM_PROVIDER", "local_keywords")

    result = extract_topics_result("fotossintese")

    assert [topic["name"] for topic in result.topics] == ["fotossintese"]


def test_local_topics_remove_conversation_fillers_and_nested_duplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NEKOMIND_LLM_PROVIDER", "local_keywords")

    result = extract_topics_result(
        "Eu gosto da cor azul preta. Eu acho muito feminina. "
        "Rosa nao me agrada. Eu gosto da cor preta. Entao custo."
    )
    names = [topic["name"].lower() for topic in result.topics]

    assert 1 <= len(names) <= 5
    assert "cor azul preta" in names
    assert "rosa nao me agrada" in names
    assert all(
        name not in {"eu gosto", "gosto", "cor preta", "rosa", "entao", "custo"} for name in names
    )


def test_local_topics_can_be_empty_when_only_generic_conversation_remains() -> None:
    adapter = get_llm_adapter("local_keywords")

    assert adapter.extract_topics("A gente nao quer fazer pouco.") == []


def test_invalid_topic_provider_fails_explicitly() -> None:
    with pytest.raises(ValueError, match="Provedor de topicos desconhecido"):
        get_llm_adapter("typo", "")


@pytest.mark.parametrize(
    "topic",
    [
        {"name": 123, "relevance": 0.5},
        {"name": "fotossintese", "relevance": float("nan")},
        {"name": "fotossintese", "relevance": True},
        {"name": "rio", "relevance": 0.5},
        {"name": "inventado", "relevance": 0.5, "notes": "[DEMO] bypass"},
        {"name": "fotossintese", "relevance": 0.5, "notes": {}},
    ],
)
def test_invalid_contract_never_passes_as_real(topic):
    from app.services.topic_extraction import _validate_topics

    with pytest.raises((ValueError, TypeError)):
        _validate_topics([topic], "Fotossintese e prioridade para plantas.")


def test_local_extracts_phrase_and_never_pads():
    from app.adapters.llm_adapter import get_llm_adapter

    adapter = get_llm_adapter("local_keywords")
    topics = adapter.extract_topics("Respiração celular. Respiração celular.")
    assert [t["name"].lower() for t in topics] == ["respiração celular"]
    assert adapter.extract_topics("e de para com") == []

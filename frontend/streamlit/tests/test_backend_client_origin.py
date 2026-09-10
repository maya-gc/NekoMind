from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import backend_client


def test_classify_backend_health_marks_demo_when_any_provider_is_mock() -> None:
    status = backend_client.classify_backend_health(
        {
            "status": "ok",
            "mode": "real",
            "asr_provider": "faster_whisper",
            "llm_provider": "mock",
        }
    )

    assert status["is_demo"] is True
    assert status["label"] == "Demonstração"


def test_session_origin_is_unknown_without_effective_provenance() -> None:
    origin = backend_client.session_origin({"status": "processing", "is_demo": False})

    assert origin["unknown"] is True
    assert origin["label"] == "Origem desconhecida"


def test_session_origin_marks_real_only_with_non_mock_provenance() -> None:
    origin = backend_client.session_origin(
        {
            "is_demo": False,
            "asr_provider_used": "faster_whisper",
            "topic_provider_used": "local",
        }
    )

    assert origin["unknown"] is False
    assert origin["is_demo"] is False
    assert origin["label"] == "Resultado real"


def test_partial_provenance_is_not_integrally_real():
    assert backend_client.session_origin(
        {"is_demo": False, "asr_provider_used": "faster_whisper"}
    )["unknown"]


def test_explicit_demo_remains_labelled_without_finished_stages():
    assert (
        backend_client.session_origin({"is_demo": True})["label"]
        == "Resultado de demonstração"
    )


def test_demo_action_refuses_unknown_mode_before_creation(monkeypatch):
    import pytest

    monkeypatch.setattr(backend_client, "health", dict)
    monkeypatch.setattr(
        backend_client, "effective_backend_status", lambda: {"is_demo": None}
    )
    monkeypatch.setattr(
        backend_client, "create_session", lambda *args: pytest.fail("must not create")
    )
    with pytest.raises(RuntimeError):
        backend_client.demo_session()

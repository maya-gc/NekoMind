"""Touch commands -> Mac bridge -> real API/SQLite -> serial result (fake capture)."""

import pytest

from app.mac.backend import LocalBackend
from app.mac.bridge import MacBridge
from app.mac.protocol import decode_line, encode_line
from tests.test_mac_bridge import Recorder, command


def mark_ready(bridge):
    bridge.state = "ready"
    bridge.diagnostics = [{"component": "test-preflight", "status": "ready", "message": "ok"}]


def test_demo_touch_to_persisted_result_and_retry(client, tmp_path):
    backend = LocalBackend(client=client)
    bridge = MacBridge(backend, Recorder(tmp_path / "capture.raw"), tmp_path / "journal.db")
    mark_ready(bridge)
    start = bridge.handle(decode_line(encode_line(command("start", "start-e2e"))))
    sid = start["session_id"]
    assert start["state"] == "recording" and start["is_demo"]
    assert bridge.handle(command("pause", "pause-e2e", sid))["state"] == "paused"
    assert bridge.handle(command("finish", "finish-e2e", sid))["state"] == "processing"
    bridge.wait_for_analysis()
    result = bridge.handle(command("finish", "finish-e2e", sid))
    assert result["type"] == "result" and result["session_id"] == sid
    assert result["topics"] and result["is_demo"] is True
    detail = client.get(f"/api/v1/sessions/{sid}").json()
    assert detail["finish_request_id"] == "finish-e2e"
    assert len(detail["metrics"]) == 6
    assert len(client.get("/api/v1/sessions").json()) == 1
    assert bridge.handle(command("retry", "retry-e2e", sid))["session_id"] != sid
    bridge.close()


def test_real_silence_never_becomes_device_result(client, tmp_path, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("NEKOMIND_MODE", "real")
    monkeypatch.setenv("NEKOMIND_ASR_PROVIDER", "faster_whisper")
    monkeypatch.setenv("NEKOMIND_LLM_PROVIDER", "local_keywords")
    get_settings.cache_clear()
    bridge = MacBridge(
        LocalBackend(client=client), Recorder(tmp_path / "capture.raw"), tmp_path / "journal.db"
    )
    mark_ready(bridge)
    sid = bridge.handle(command("start", "start-real"))["session_id"]
    bridge.handle(command("finish", "finish-real", sid))
    bridge.wait_for_analysis()
    result = bridge.handle(command("status", "recover", sid))
    assert result["type"] == "error"
    detail = client.get(f"/api/v1/sessions/{sid}").json()
    assert detail["status"] == "error" and detail["clarity_score"] is None
    assert detail["topics"] == detail["metrics"] == []
    bridge.close()


def test_real_pipeline_uses_local_extractor_and_correct_session(client, tmp_path, monkeypatch):
    from app.config import get_settings
    from app.services import audio_processing, transcription
    from app.services.transcription import TranscriptionResult

    monkeypatch.setenv("NEKOMIND_MODE", "real")
    monkeypatch.setenv("NEKOMIND_ASR_PROVIDER", "faster_whisper")
    monkeypatch.setenv("NEKOMIND_LLM_PROVIDER", "local_keywords")
    get_settings.cache_clear()
    # ASR and VAD policy are substituted, extractor/API/SQLite/bridge are real code.
    monkeypatch.setattr(audio_processing, "validate_speech", lambda path: {"speech_seconds": 1})
    text = "Respiração celular. Fotossíntese nas plantas usa luz."
    monkeypatch.setattr(
        transcription,
        "transcribe_audio_result",
        lambda path, **kwargs: TranscriptionResult(text, "faster_whisper", False),
    )
    bridge = MacBridge(
        LocalBackend(client=client), Recorder(tmp_path / "capture.raw"), tmp_path / "journal.db"
    )
    mark_ready(bridge)
    sid = bridge.handle(command("start", "real-text"))["session_id"]
    bridge.handle(command("finish", "real-text-finish", sid))
    bridge.wait_for_analysis()
    result = bridge.handle(command("status", "real-text-status", sid))
    assert result["type"] == "result" and result["is_demo"] is False
    assert "Respiração celular" in result["topics"]
    assert all(
        t["session_id"] == sid for t in client.get(f"/api/v1/sessions/{sid}").json()["topics"]
    )
    bridge.close()


@pytest.mark.parametrize("graph_available", [True, False])
def test_real_guided_graph_is_persisted_once_for_the_selected_session(client, tmp_path, monkeypatch, graph_available):
    from app.config import get_settings
    from app.services import audio_processing, semantic_graph, transcription
    from app.services.transcription import TranscriptionResult

    monkeypatch.setenv("NEKOMIND_MODE", "real")
    monkeypatch.setenv("NEKOMIND_ASR_PROVIDER", "faster_whisper")
    monkeypatch.setenv("NEKOMIND_LLM_PROVIDER", "local_keywords")
    get_settings.cache_clear()
    monkeypatch.setattr(audio_processing, "validate_speech", lambda path: {"speech_seconds": 1})
    spoken = "Fotossíntese nas plantas usa luz solar para produzir energia."
    monkeypatch.setattr(
        transcription,
        "transcribe_audio_result",
        lambda path, **kwargs: TranscriptionResult(spoken, "faster_whisper", False),
    )
    calls = []

    def graph(points, transcript, model):
        calls.append((points, transcript, model))
        if not graph_available:
            raise semantic_graph.SemanticGraphError("local model offline")
        return {"status": "completed", "method_version": "local-relation-graph-v1", "edges": [
            {"point_index": 0, "speech_excerpt": spoken, "relation": "support_hint"}
        ]}

    monkeypatch.setattr(semantic_graph, "build_semantic_graph", graph)
    content = client.post("/api/v1/contents", json={
        "title": "Fotossíntese", "text": "Fotossíntese nas plantas usa luz solar.",
    }).json()
    assert client.put("/api/v1/experience/selection", json={"content_id": content["id"]}).status_code == 200
    bridge = MacBridge(LocalBackend(client=client), Recorder(tmp_path / "capture.raw"), tmp_path / "journal.db")
    mark_ready(bridge)
    sid = bridge.handle(command("start", "guided-graph-start"))["session_id"]
    bridge.handle(command("finish", "guided-graph-finish", sid))
    bridge.wait_for_analysis()
    first = client.get(f"/api/v1/sessions/{sid}").json()
    bridge.handle(command("finish", "guided-graph-finish", sid))
    second = client.get(f"/api/v1/sessions/{sid}").json()
    assert first["content_report"] == second["content_report"]
    assert first["content_report"]["semantic_graph"]["status"] == (
        "completed" if graph_available else "unavailable"
    )
    assert first["content_report"]["content_id"] == content["id"]
    assert len(calls) == 1
    assert calls[0][1] == spoken
    bridge.close()

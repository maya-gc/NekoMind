"""Touch commands -> Mac bridge -> real API/SQLite -> serial result (fake capture)."""

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

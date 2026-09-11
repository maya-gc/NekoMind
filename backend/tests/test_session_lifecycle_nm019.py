"""Lifecycle coverage for NM-009..011 and NM-016 backend behavior."""

from __future__ import annotations

import json
import math


def _pcm_tone(seconds: float, amplitude: int = 6000, sample_rate: int = 16000) -> bytes:
    count = int(seconds * sample_rate)
    samples = [int(amplitude * math.sin(2 * math.pi * 220 * i / sample_rate)) for i in range(count)]
    return b"".join(sample.to_bytes(2, "little", signed=True) for sample in samples)


def _upload_pcm(client, session_id: int, payload: bytes, sequence: int = 0) -> dict:
    files = {"file": ("chunk.raw", payload, "application/octet-stream")}
    data = {"sequence": str(sequence), "audio_format": "pcm_s16le", "sample_rate": "16000"}
    response = client.post(f"/api/v1/sessions/{session_id}/audio", files=files, data=data)
    assert response.status_code == 201
    return response.json()


def test_recover_analyze_reuses_persisted_transcription_and_records_journey(
    client, monkeypatch
) -> None:
    from app.services import topic_extraction, transcription
    from app.services.transcription import TranscriptionResult

    session_id = client.post("/api/v1/sessions", json={"title": "Recovery"}).json()["id"]
    created = client.get(f"/api/v1/sessions/{session_id}").json()
    assert created["journey"] == {}
    recording = client.post(
        f"/api/v1/sessions/{session_id}/capture-state",
        json={"state": "recording"},
    ).json()
    assert recording["journey"]["capture"]["status"] == "running"
    _upload_pcm(client, session_id, _pcm_tone(1.0))

    calls = {"asr": 0, "topics": 0}

    def transcribe_once(_path, *, provider=None):
        calls["asr"] += 1
        return TranscriptionResult(
            text="[DEMO] fotossintese usa luz e agua.",
            provider=provider or "mock",
            is_demo=True,
        )

    def fail_topics_once(_text, *, provider=None):
        calls["topics"] += 1
        if calls["topics"] == 1:
            raise ValueError("extrator indisponivel")
        return topic_extraction.TopicExtractionResult(
            topics=[{"name": "fotossintese", "relevance": 0.9, "notes": None}],
            provider=provider or "mock",
            is_demo=True,
        )

    monkeypatch.setattr(transcription, "transcribe_audio_result", transcribe_once)
    monkeypatch.setattr(topic_extraction, "extract_topics_result", fail_topics_once)

    failed = client.post(
        f"/api/v1/sessions/{session_id}/finish",
        json={"request_id": "finish-recovery"},
    )
    failed_detail = failed.json()
    assert failed.status_code == 500
    assert failed_detail["status"] == "error"
    assert failed_detail["transcription"] == "[DEMO] fotossintese usa luz e agua."
    assert failed_detail["journey"]["capture"]["status"] == "completed"
    assert failed_detail["journey"]["capture"]["duration_ms"] == 1000
    assert failed_detail["journey"]["transcription"]["status"] == "completed"
    assert failed_detail["journey"]["topics"]["status"] == "error"

    recovered = client.post(
        f"/api/v1/sessions/{session_id}/recover",
        json={"action": "analyze", "request_id": "recover-analyze"},
    )
    recovered_detail = recovered.json()

    assert recovered.status_code == 200
    assert recovered_detail["status"] == "completed"
    assert calls["asr"] == 1
    assert recovered_detail["transcription"] == "[DEMO] fotossintese usa luz e agua."
    assert recovered_detail["journey"]["transcription"]["status"] == "completed"
    assert recovered_detail["journey"]["topics"]["status"] == "completed"
    assert recovered_detail["journey"]["result"]["duration_ms"] >= 0

    subject = client.patch(
        f"/api/v1/sessions/{session_id}/subject",
        json={"subject": "Fotossintese", "confirmed": True},
    ).json()
    assert subject["subject"] == "Fotossintese"
    assert subject["subject_confirmed"] is True
    history = client.get("/api/v1/history/subjects/Fotossintese").json()
    assert history["subject"] == "Fotossintese"
    assert history["method_version"] == "heuristic-v1"
    assert history["disclaimer"]
    assert [point["session_id"] for point in history["points"]] == [session_id]


def test_recover_analyze_uses_persisted_transcription_when_raw_audio_is_gone(
    client, monkeypatch
) -> None:
    from app.config import get_settings
    from app.services import topic_extraction, transcription
    from app.services.transcription import TranscriptionResult

    session_id = client.post("/api/v1/sessions", json={"title": "Retry sem raw"}).json()["id"]
    _upload_pcm(client, session_id, _pcm_tone(1.0))
    calls = {"asr": 0, "topics": 0}

    def transcribe_once(_path, *, provider=None):
        calls["asr"] += 1
        return TranscriptionResult(
            text="[DEMO] plantas usam luz.",
            provider=provider or "mock",
            is_demo=True,
        )

    def topics_second_try(_text, *, provider=None):
        calls["topics"] += 1
        if calls["topics"] == 1:
            raise ValueError("topics unavailable")
        return topic_extraction.TopicExtractionResult(
            topics=[{"name": "plantas", "relevance": 0.8, "notes": None}],
            provider=provider or "mock",
            is_demo=True,
        )

    monkeypatch.setattr(transcription, "transcribe_audio_result", transcribe_once)
    monkeypatch.setattr(topic_extraction, "extract_topics_result", topics_second_try)

    failed = client.post(f"/api/v1/sessions/{session_id}/finish", json={"request_id": "raw-fail"})
    assert failed.status_code == 500
    session_dir = get_settings().storage_dir / f"session_{session_id}"
    for raw in session_dir.glob("*.raw"):
        raw.unlink()
    wav = session_dir / "session.wav"
    wav.unlink(missing_ok=True)

    recovered = client.post(
        f"/api/v1/sessions/{session_id}/recover",
        json={"action": "analyze", "request_id": "raw-retry"},
    )

    assert recovered.status_code == 200
    assert recovered.json()["status"] == "completed"
    assert calls["asr"] == 1


def test_confirmed_delete_removes_session_audio_and_preserves_other_sessions(client) -> None:
    from app.config import get_settings

    first_id = client.post("/api/v1/sessions", json={"title": "Excluir"}).json()["id"]
    second_id = client.post("/api/v1/sessions", json={"title": "Preservar"}).json()["id"]
    _upload_pcm(client, first_id, _pcm_tone(0.5))
    _upload_pcm(client, second_id, _pcm_tone(0.5))
    client.post(
        f"/api/v1/sessions/{first_id}/capture-state",
        json={"state": "error", "error_code": "test_stopped", "error_message": "controlled"},
    )
    storage_dir = get_settings().storage_dir
    first_path = next((storage_dir / f"session_{first_id}").glob("chunk_*.raw"))
    second_path = next((storage_dir / f"session_{second_id}").glob("chunk_*.raw"))
    assert first_path.exists()
    assert second_path.exists()

    rejected = client.request("DELETE", f"/api/v1/sessions/{first_id}", json={"confirmed": False})
    assert rejected.status_code == 409
    assert first_path.exists()

    deleted = client.request("DELETE", f"/api/v1/sessions/{first_id}", json={"confirmed": True})
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert deleted.json()["session_id"] == first_id
    assert not first_path.exists()
    assert second_path.exists()
    assert client.get(f"/api/v1/sessions/{first_id}").status_code == 404
    assert client.get(f"/api/v1/sessions/{second_id}").status_code == 200

    repeated = client.request("DELETE", f"/api/v1/sessions/{first_id}", json={"confirmed": True})
    assert repeated.status_code == 200
    assert repeated.json()["deleted"] is False


def test_delete_cleans_mac_capture_paths_and_session_command_receipts(client, monkeypatch) -> None:
    from app.config import get_settings
    from app.database.connection import SessionLocal
    from app.database.operations import OperatorCommand

    settings = get_settings()
    mac_dir = settings.storage_dir.parent / "mac-fixture"
    monkeypatch.setenv("NEKOMIND_MAC_DATA_DIR", str(mac_dir))
    get_settings.cache_clear()
    session_id = client.post("/api/v1/sessions", json={"title": "Mac cleanup"}).json()["id"]
    other_id = client.post("/api/v1/sessions", json={"title": "Other cleanup"}).json()["id"]
    _upload_pcm(client, session_id, _pcm_tone(0.5))
    client.post(
        f"/api/v1/sessions/{session_id}/capture-state",
        json={"state": "error", "error_code": "test_stopped"},
    )
    capture_dir = mac_dir / "capture"
    capture_dir.mkdir(parents=True)
    target_raw = capture_dir / f"capture_{session_id}.raw"
    target_manifest = capture_dir / f"capture_{session_id}.manifest"
    other_raw = capture_dir / f"capture_{other_id}.raw"
    target_raw.write_bytes(b"private raw")
    target_manifest.write_text("private manifest")
    other_raw.write_bytes(b"other raw")
    with SessionLocal() as db:
        db.add(
            OperatorCommand(
                request_id="delete-target",
                payload=json.dumps(
                    {
                        "request_id": "delete-target",
                        "session_id": session_id,
                        "command": "reset",
                        "confirmed": True,
                        "mode": None,
                    }
                ),
                response=json.dumps(
                    {
                        "request_id": "delete-target",
                        "session_id": session_id,
                        "type": "result",
                        "state": "completed",
                        "topics": ["private"],
                    }
                ),
                status="done",
            )
        )
        db.add(
            OperatorCommand(
                request_id="keep-other",
                payload=json.dumps(
                    {
                        "request_id": "keep-other",
                        "session_id": other_id,
                        "command": "reset",
                        "confirmed": True,
                        "mode": None,
                    }
                ),
                status="done",
            )
        )
        db.commit()

    deleted = client.request("DELETE", f"/api/v1/sessions/{session_id}", json={"confirmed": True})

    assert deleted.status_code == 200
    assert not target_raw.exists()
    assert not target_manifest.exists()
    assert other_raw.exists()
    with SessionLocal() as db:
        assert db.get(OperatorCommand, "delete-target") is None
        assert db.get(OperatorCommand, "keep-other") is not None
    get_settings.cache_clear()


def test_delete_and_processing_claims_are_mutually_exclusive(client) -> None:
    from app.database.connection import SessionLocal
    from app.database.models import SessionStatus
    from app.repositories.session_repository import SessionRepository

    session_id = client.post("/api/v1/sessions", json={"title": "CAS"}).json()["id"]
    client.post(
        f"/api/v1/sessions/{session_id}/capture-state",
        json={"state": "error", "error_code": "controlled"},
    )
    with SessionLocal() as db:
        claimed = SessionRepository(db).claim_deletion(
            session_id,
            allowed_statuses={SessionStatus.error},
        )
        assert claimed is not None
    with SessionLocal() as db:
        processing = SessionRepository(db).claim_processing(
            session_id,
            "retry-after-delete",
            {SessionStatus.error, SessionStatus.recovery, SessionStatus.paused},
        )
        assert processing is None


def test_subject_history_defaults_to_latest_metric_method_version(client) -> None:
    from app.database.connection import SessionLocal
    from app.database.models import SessionStatus, StudySession

    with SessionLocal() as db:
        older = StudySession(
            status=SessionStatus.completed,
            subject="Fotossintese",
            subject_confirmed=True,
            metric_method_version="heuristic-v1",
            duration_seconds=10,
            clarity_score=3,
            is_demo=True,
        )
        newer = StudySession(
            status=SessionStatus.completed,
            subject="Fotossintese",
            subject_confirmed=True,
            metric_method_version="heuristic-v2",
            duration_seconds=12,
            clarity_score=4,
            is_demo=True,
        )
        db.add_all([older, newer])
        db.commit()

    latest = client.get("/api/v1/history/subjects/Fotossintese").json()
    explicit = client.get(
        "/api/v1/history/subjects/Fotossintese",
        params={"method_version": "heuristic-v1"},
    ).json()

    assert latest["method_version"] == "heuristic-v2"
    assert latest["available_method_versions"] == ["heuristic-v2", "heuristic-v1"]
    assert len(latest["points"]) == 1
    assert explicit["method_version"] == "heuristic-v1"
    assert len(explicit["points"]) == 1

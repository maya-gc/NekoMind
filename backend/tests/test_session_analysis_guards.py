"""Analysis guards for real/demo origin, speech validation and idempotence."""

from __future__ import annotations

import math
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest


def _pcm_tone(seconds: float, amplitude: int = 6000, sample_rate: int = 16000) -> bytes:
    count = int(seconds * sample_rate)
    samples = [int(amplitude * math.sin(2 * math.pi * 220 * i / sample_rate)) for i in range(count)]
    return b"".join(sample.to_bytes(2, "little", signed=True) for sample in samples)


def _upload_pcm(client, session_id: int, payload: bytes, sequence: int = 0) -> None:
    files = {"file": ("chunk.raw", payload, "application/octet-stream")}
    data = {"sequence": str(sequence), "audio_format": "pcm_s16le", "sample_rate": "16000"}
    response = client.post(f"/api/v1/sessions/{session_id}/audio", files=files, data=data)
    assert response.status_code == 201


def test_demo_silence_still_completes_and_is_identified(client) -> None:
    session_id = client.post("/api/v1/sessions", json={}).json()["id"]
    _upload_pcm(client, session_id, b"\x00\x00" * 16000)

    response = client.post(
        f"/api/v1/sessions/{session_id}/finish",
        json={"request_id": "finish-demo-1"},
    )
    detail = response.json()

    assert response.status_code == 200
    assert detail["status"] == "completed"
    assert detail["ended_at"] is not None
    assert detail["is_demo"] is True
    assert detail["asr_provider_used"] == "mock"
    assert detail["topic_provider_used"] == "mock"


def test_real_mode_rejects_silence_without_metrics_or_topics(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEKOMIND_ASR_PROVIDER", "faster_whisper")
    monkeypatch.setenv("NEKOMIND_LLM_PROVIDER", "local_keywords")

    from app.config import get_settings

    get_settings.cache_clear()
    session_id = client.post("/api/v1/sessions", json={}).json()["id"]
    _upload_pcm(client, session_id, b"\x00\x00" * 16000)

    response = client.post(
        f"/api/v1/sessions/{session_id}/finish",
        json={"request_id": "finish-real-silence"},
    )
    detail = response.json()

    assert response.status_code == 422
    assert detail["status"] == "error"
    assert detail["error_code"] == "audio_unusable"
    assert detail["clarity_score"] is None
    assert detail["topics"] == []
    assert detail["metrics"] == []


def test_finish_is_idempotent_and_does_not_duplicate_rows(client) -> None:
    session_id = client.post(
        "/api/v1/sessions",
        json={"title": "Idempotencia", "request_id": "start-1"},
    ).json()["id"]
    repeated_start = client.post(
        "/api/v1/sessions",
        json={"title": "Idempotencia", "request_id": "start-1"},
    ).json()
    assert repeated_start["id"] == session_id

    _upload_pcm(client, session_id, _pcm_tone(1.0))

    first = client.post(
        f"/api/v1/sessions/{session_id}/finish",
        json={"request_id": "finish-1"},
    ).json()
    second = client.post(
        f"/api/v1/sessions/{session_id}/finish",
        json={"request_id": "finish-1"},
    ).json()

    assert first["status"] == "completed"
    assert second["id"] == first["id"]
    assert len(second["topics"]) == len(first["topics"])
    assert len(second["metrics"]) == len(first["metrics"])


def test_concurrent_finish_returns_processing_without_waiting_for_owner(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import transcription
    from app.services.transcription import TranscriptionResult

    session_id = client.post("/api/v1/sessions", json={"title": "Concorrencia"}).json()["id"]
    _upload_pcm(client, session_id, _pcm_tone(1.0))

    def slow_transcribe(_path, **_kwargs):
        time.sleep(0.35)
        return TranscriptionResult(
            text="[DEMO] Fotossintese usa luz e agua.",
            provider="mock",
            is_demo=True,
        )

    monkeypatch.setattr(transcription, "transcribe_audio_result", slow_transcribe)

    def finish(request_id: str):
        from app.database.connection import SessionLocal
        from app.repositories.session_repository import SessionRepository
        from app.services import session_analysis

        start = time.monotonic()
        db = SessionLocal()
        try:
            session = SessionRepository(db).get(session_id)
            assert session is not None
            result = session_analysis.analyze_session(db, session, finish_request_id=request_id)
            return time.monotonic() - start, result.status.value
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(finish, "finish-owner")
        time.sleep(0.05)
        second_elapsed, second_status = finish("finish-replay")
        first_elapsed, first_status = first.result(timeout=2)

    assert second_elapsed < 0.2
    assert second_status == "processing"
    assert first_elapsed >= 0.3
    assert first_status == "completed"


def test_finish_returns_persisted_error_when_analysis_fails(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import topic_extraction

    session_id = client.post("/api/v1/sessions", json={"title": "Falha topico"}).json()["id"]
    _upload_pcm(client, session_id, _pcm_tone(1.0))

    def fail_topics(_text):
        raise ValueError("payload invalido")

    monkeypatch.setattr(topic_extraction, "extract_topics_result", fail_topics)

    response = client.post(
        f"/api/v1/sessions/{session_id}/finish",
        json={"request_id": "finish-topic-fail"},
    )
    detail = response.json()
    repeated = client.post(
        f"/api/v1/sessions/{session_id}/finish",
        json={"request_id": "finish-topic-fail"},
    ).json()

    assert response.status_code == 500
    assert detail["status"] == "error"
    assert detail["error_code"] == "analysis_failed"
    assert detail["asr_provider_used"] == "mock"
    assert detail["topic_provider_used"] == "mock"
    assert repeated["status"] == "error"


def test_concurrent_start_with_same_request_id_is_idempotent(client) -> None:
    payload = {
        "title": "Inicio concorrente",
        "request_id": "start-race-1",
        "capture_source": "mac",
        "device_session_id": "device-1",
    }

    def create(body):
        return client.post("/api/v1/sessions", json=body)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(create, payload)
        second = pool.submit(create, payload)
        responses = [first.result(timeout=2), second.result(timeout=2)]

    assert {response.status_code for response in responses} == {201}
    ids = {response.json()["id"] for response in responses}
    assert len(ids) == 1

    conflict = client.post(
        "/api/v1/sessions",
        json={**payload, "capture_source": "other"},
    )
    assert conflict.status_code == 409


def test_cancel_processing_session_prevents_late_analysis_result(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.database.connection import SessionLocal
    from app.database.models import StudySession
    from app.services import transcription
    from app.services.transcription import TranscriptionResult

    session_id = client.post("/api/v1/sessions", json={"title": "Cancelar processing"}).json()["id"]
    _upload_pcm(client, session_id, _pcm_tone(1.0))
    entered = Event()
    release = Event()

    def blocked_transcribe(_path, *, provider=None):
        entered.set()
        assert release.wait(timeout=3)
        return TranscriptionResult(
            text="[DEMO] conteudo tardio nao deve salvar resultado.",
            provider=provider or "mock",
            is_demo=True,
        )

    monkeypatch.setattr(transcription, "transcribe_audio_result", blocked_transcribe)

    with ThreadPoolExecutor(max_workers=1) as pool:
        finish = pool.submit(
            lambda: client.post(
                f"/api/v1/sessions/{session_id}/finish",
                json={"request_id": "finish-cancelled"},
            )
        )
        assert entered.wait(timeout=3)
        cancelled = client.post(
            f"/api/v1/sessions/{session_id}/cancel",
            json={"confirmed": True, "request_id": "cancel-processing"},
        )
        release.set()
        finish_response = finish.result(timeout=3)

    with SessionLocal() as db:
        persisted = db.get(StudySession, session_id)
        assert persisted is not None
        assert persisted.status.value == "cancelled"
        assert persisted.transcription is None
        assert persisted.clarity_score is None
        assert persisted.topics == []
        assert persisted.metrics == []

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert finish_response.status_code in {200, 422}

"""Backend contract tests for capture state and audio idempotency."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest

from app.api.routes_sessions import update_capture_state
from app.config import get_settings
from app.database.connection import SessionLocal
from app.database.models import AudioChunk, SessionStatus
from app.repositories.session_repository import SessionRepository
from app.schemas.session import CaptureStateUpdate
from app.services import audio_ingestion


def _create_session(client) -> int:
    response = client.post(
        "/api/v1/sessions",
        json={"title": "Contrato audio", "request_id": f"start-audio-{uuid4().hex}"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _upload(client, session_id: int, payload: bytes, sequence: int = 0):
    files = {"file": ("chunk.raw", payload, "application/octet-stream")}
    data = {"sequence": str(sequence), "audio_format": "pcm_s16le", "sample_rate": "16000"}
    return client.post(f"/api/v1/sessions/{session_id}/audio", files=files, data=data)


def test_upload_chunk_is_idempotent_for_same_sequence_and_bytes(client) -> None:
    session_id = _create_session(client)
    payload = b"\x01\x00" * 16000

    first = _upload(client, session_id, payload, sequence=0)
    second = _upload(client, session_id, payload, sequence=0)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["chunk_id"] == first.json()["chunk_id"]
    assert second.json()["deduplicated"] is True


def test_upload_rejects_changed_duplicate_and_upload_after_analysis(client) -> None:
    session_id = _create_session(client)
    assert _upload(client, session_id, b"\x01\x00" * 16000, sequence=0).status_code == 201

    changed = _upload(client, session_id, b"\x02\x00" * 16000, sequence=0)
    assert changed.status_code == 409

    assert client.post(f"/api/v1/sessions/{session_id}/finish").status_code == 200
    late = _upload(client, session_id, b"\x03\x00" * 16000, sequence=1)
    assert late.status_code == 409


def test_upload_accepts_chunks_while_capture_is_paused(client) -> None:
    session_id = _create_session(client)
    paused = client.post(
        f"/api/v1/sessions/{session_id}/capture-state",
        json={"request_id": "pause-before-upload", "state": "paused"},
    )

    uploaded = _upload(client, session_id, b"\x04\x00" * 16000, sequence=0)

    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    assert uploaded.status_code == 201
    assert uploaded.json()["sequence"] == 0


def test_capture_state_updates_recording_paused_and_error(client) -> None:
    session_id = _create_session(client)

    paused = client.post(
        f"/api/v1/sessions/{session_id}/capture-state",
        json={"request_id": "pause-1", "state": "paused"},
    )
    resumed = client.post(
        f"/api/v1/sessions/{session_id}/capture-state",
        json={"request_id": "resume-1", "state": "recording"},
    )
    errored = client.post(
        f"/api/v1/sessions/{session_id}/capture-state",
        json={
            "request_id": "capture-error-1",
            "state": "error",
            "error_code": "capture_unavailable",
            "error_message": "Microfone indisponivel",
        },
    )

    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "recording"
    assert errored.status_code == 200
    assert errored.json()["status"] == "error"
    assert errored.json()["error_code"] == "capture_unavailable"
    assert errored.json()["ended_at"] is not None


def test_capture_state_does_not_overwrite_processing_from_stale_session(client) -> None:
    session_id = _create_session(client)
    stale_db = SessionLocal()
    fresh_db = SessionLocal()
    verify_db = SessionLocal()
    try:
        stale_session = SessionRepository(stale_db).get(session_id)
        assert stale_session is not None
        assert stale_session.status == SessionStatus.recording

        fresh_session = SessionRepository(fresh_db).get(session_id)
        assert fresh_session is not None
        fresh_session.status = SessionStatus.processing
        fresh_db.commit()

        result = update_capture_state(
            session_id,
            CaptureStateUpdate(request_id="stale-pause", state="paused"),
            db=stale_db,
        )

        persisted = SessionRepository(verify_db).get(session_id)
        assert persisted is not None
        assert result.status == SessionStatus.processing
        assert persisted.status == SessionStatus.processing
    finally:
        stale_db.close()
        fresh_db.close()
        verify_db.close()


def test_concurrent_identical_uploads_return_one_chunk(client) -> None:
    session_id = _create_session(client)
    payload = b"\x05\x00" * 16000

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(_upload, client, session_id, payload, 0)
        second = pool.submit(_upload, client, session_id, payload, 0)
        responses = [first.result(timeout=2), second.result(timeout=2)]

    assert sorted(response.status_code for response in responses) == [200, 201]
    assert len({response.json()["chunk_id"] for response in responses}) == 1


def test_concurrent_different_uploads_conflict(client) -> None:
    session_id = _create_session(client)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(_upload, client, session_id, b"\x06\x00" * 16000, 0)
        second = pool.submit(_upload, client, session_id, b"\x07\x00" * 16000, 0)
        responses = [first.result(timeout=2), second.result(timeout=2)]

    assert sorted(response.status_code for response in responses) == [201, 409]


def test_finish_rejects_audio_sequence_gaps_without_merging(client) -> None:
    session_id = _create_session(client)
    files = {"file": ("chunk.raw", b"\x08\x00" * 16000, "application/octet-stream")}
    response = client.post(
        f"/api/v1/sessions/{session_id}/audio",
        files=files,
        data={"sequence": "1", "audio_format": "pcm_s16le", "sample_rate": "16000"},
    )

    assert response.status_code == 409


def test_upload_oversized_chunk_returns_payload_too_large(client) -> None:
    session_id = _create_session(client)
    payload = b"\x0b\x00" * ((16000 * 30) + 1)

    response = _upload(client, session_id, payload, sequence=0)

    assert response.status_code == 413


def test_failed_chunk_commit_removes_attempt_file_and_publishes_no_manifest(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id = _create_session(client)
    db = SessionLocal()
    try:
        session = SessionRepository(db).get(session_id)
        assert session is not None
        session_dir = Path(get_settings().storage_dir) / f"session_{session_id}"
        before_files = set(session_dir.glob("*.raw"))

        def fail_commit() -> None:
            raise RuntimeError("commit failed")

        monkeypatch.setattr(db, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="commit failed"):
            audio_ingestion.save_chunk(db, session, b"\x09\x00" * 16000, 0)

        db.rollback()
        assert db.query(AudioChunk).filter(AudioChunk.session_id == session_id).count() == 0
        assert set(session_dir.glob("*.raw")) == before_files
    finally:
        db.close()


def test_chunk_commit_survives_refresh_failure_and_keeps_manifest_file(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id = _create_session(client)
    db = SessionLocal()
    try:
        session = SessionRepository(db).get(session_id)
        assert session is not None
        real_refresh = db.refresh

        def fail_chunk_refresh(instance) -> None:
            if isinstance(instance, AudioChunk):
                from sqlalchemy.exc import SQLAlchemyError

                raise SQLAlchemyError("refresh failed")
            real_refresh(instance)

        monkeypatch.setattr(db, "refresh", fail_chunk_refresh)
        chunk, deduplicated = audio_ingestion.save_chunk(db, session, b"\x0a\x00" * 16000, 0)
        assert deduplicated is False
        chunk_id = chunk.id
    finally:
        db.close()

    verify_db = SessionLocal()
    try:
        persisted = verify_db.get(AudioChunk, chunk_id)
        assert persisted is not None
        assert Path(persisted.file_path).read_bytes() == b"\x0a\x00" * 16000
    finally:
        verify_db.close()

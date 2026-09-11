"""Local operational boundary; synthetic sessions only."""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest


def publish(client, sid=None, state="ready", **kw):
    return client.post(
        "/api/v1/experience/bridge",
        json={
            "session_id": sid,
            "state": state,
            "is_demo": True,
            **kw,
        },
    )


def test_public_surface_never_exposes_session_content(client):
    row = client.post("/api/v1/sessions", json={"request_id": "private-one"}).json()
    public = client.get("/api/v1/experience/public", headers={"Authorization": ""})
    assert public.status_code == 200
    assert public.json()["session_id"] is None
    assert "transcription" not in public.text
    assert row["id"] > 0


def test_presenter_requires_local_operator_token(client):
    response = client.get("/api/v1/experience/presenter", headers={"Authorization": ""})
    assert response.status_code == 401


def test_destructive_commands_require_confirmation_and_replays_are_safe(client):
    payload = {"command": "reset", "request_id": "reset-one", "session_id": None}
    assert client.post("/api/v1/experience/commands", json=payload).status_code == 409
    payload["confirmed"] = True
    first = client.post("/api/v1/experience/commands", json=payload)
    second = client.post("/api/v1/experience/commands", json=payload)
    assert first.status_code == 200
    assert first.json() == second.json()
    payload["command"] = "cancel"
    assert client.post("/api/v1/experience/commands", json=payload).status_code == 409


def test_bridge_cannot_claim_completed_without_persisted_result(client):
    row = client.post("/api/v1/sessions", json={"request_id": "unfinished"}).json()
    response = client.post(
        "/api/v1/experience/bridge",
        json={
            "session_id": row["id"],
            "state": "completed",
            "is_demo": True,
        },
    )
    assert response.status_code == 409


def test_demo_providers_do_not_import_real_model(client, monkeypatch):
    import builtins

    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        assert name not in {"faster_whisper", "sounddevice"}
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    response = client.get("/api/v1/experience/providers")
    assert response.status_code == 200
    assert all(c["status"] in {"ready", "skipped"} for c in response.json()["components"])


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/sessions",
        "/api/v1/dashboard/summary",
        "/api/v1/experience/commands",
        "/api/v1/experience/providers",
    ],
)
def test_private_routes_require_token(client, path):
    assert client.get(path, headers={"Authorization": ""}).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_token_file_is_private_and_reused(client):
    from app.security import operator_token, operator_token_path

    assert operator_token() == operator_token()
    assert operator_token_path().stat().st_mode & 0o777 == 0o600


def test_expired_capture_heartbeat_never_remains_recording(client, monkeypatch):
    from app.api import routes_experience

    sid = client.post("/api/v1/sessions", json={"request_id": "heart"}).json()["id"]
    publish(client, sid, "recording", voice={"level": 40, "clipping": False, "quality": "ok"})
    snapshot = client.get("/api/v1/experience/public").json()
    assert snapshot["state"] == "recording"
    now = routes_experience.time.time()
    monkeypatch.setattr(routes_experience.time, "time", lambda: now + 30)
    snapshot = client.get("/api/v1/experience/public").json()
    assert snapshot["state"] == "recovery"
    assert snapshot["voice"] is None


def test_result_requires_actual_origins_and_never_exposes_transcription(client):
    from app.database.connection import SessionLocal
    from app.database.models import SessionStatus, StudySession

    sid = client.post("/api/v1/sessions", json={"request_id": "result"}).json()["id"]
    with SessionLocal() as db:
        session = db.get(StudySession, sid)
        session.status = SessionStatus.completed
        session.transcription = "SYNTHETIC PRIVATE TEXT DO NOT DISPLAY"
        db.commit()
    assert publish(client, sid, "completed").status_code == 409
    with SessionLocal() as db:
        session = db.get(StudySession, sid)
        session.asr_provider_used = session.topic_provider_used = "mock"
        db.commit()
    assert publish(client, sid, "completed").status_code == 200
    response = client.get("/api/v1/experience/public")
    assert response.json()["state"] == "completed"
    assert "SYNTHETIC PRIVATE" not in response.text
    assert "transcription" not in response.text


def test_fair_result_exposes_process_evidence_without_exposing_transcription(client):
    from app.database.connection import SessionLocal
    from app.database.models import SessionStatus, StudySession, Topic

    sid = client.post("/api/v1/sessions", json={"request_id": "fair-evidence"}).json()["id"]
    assert (
        client.post(
            "/api/v1/experience/bridge",
            json={"session_id": sid, "state": "recording", "is_demo": False},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/experience/commands",
            json={
                "request_id": "fair-evidence-mode",
                "command": "status",
                "session_id": sid,
                "mode": "fair",
            },
        ).status_code
        == 200
    )
    with SessionLocal() as db:
        session = db.get(StudySession, sid)
        session.status = SessionStatus.completed
        session.mode = "real"
        session.is_demo = False
        session.transcription = "Eu mencionei azul, preto, rosa e estilo nesta fala privada."
        session.duration_seconds = 21.45
        session.audio_validation = json.dumps({"speech_seconds": 12.3})
        session.asr_provider_used = "faster_whisper"
        session.topic_provider_used = "local_keywords"
        session.journey_json = json.dumps(
            {
                step: {
                    "status": "completed",
                    "duration_ms": 100,
                    "provider": provider,
                    "is_demo": False,
                }
                for step, provider in (
                    ("capture", "mac_microphone"),
                    ("transcription", "faster_whisper"),
                    ("topics", "local_keywords"),
                    ("result", "backend"),
                )
            }
        )
        session.topics.extend(
            [Topic(name=name, relevance=0.9) for name in ("azul", "preto", "rosa", "estilo")]
        )
        db.commit()

    published = client.post(
        "/api/v1/experience/bridge",
        json={"session_id": sid, "state": "completed", "is_demo": False},
    )
    assert published.status_code == 200

    response = client.get("/api/v1/experience/public")
    payload = response.json()
    assert payload["result"]["summary"] == "Voz captada e processada."
    assert payload["result"]["evidence"] == {
        "speech_detected": True,
        "recognized_word_count": 10,
        "completed_steps": 4,
        "local_processing": True,
    }
    assert "fala privada" not in response.text
    assert "transcription" not in payload
    assert "transcription" not in payload["result"]


def test_reset_clears_visitor_and_rejects_late_publish(client):
    sid = client.post("/api/v1/sessions", json={"request_id": "visitor"}).json()["id"]
    publish(client, sid, "recording")
    first = client.get("/api/v1/experience/public").json()
    cmd = {"request_id": "clear-visitor", "command": "reset", "session_id": sid, "confirmed": True}
    assert client.post("/api/v1/experience/commands", json=cmd).status_code == 200
    ack = {
        "response": {
            "request_id": "clear-visitor",
            "type": "state",
            "session_id": None,
            "state": "idle",
        }
    }
    assert client.post("/api/v1/experience/commands/clear-visitor/ack", json=ack).status_code == 200
    assert client.post("/api/v1/experience/commands/clear-visitor/ack", json=ack).status_code == 200
    cleared = client.get("/api/v1/experience/public").json()
    assert cleared["generation"] == first["generation"] + 1
    assert cleared["session_id"] is None and cleared["result"] is None
    assert cleared["journey"] == [] and cleared["voice"] is None
    assert publish(client, sid, "recording").status_code == 409


def test_command_queue_durable_until_correct_ack_and_concurrent_dedup(client):
    cmd = {"request_id": "diagnostic-one", "command": "diagnose"}
    with ThreadPoolExecutor(4) as pool:
        results = list(
            pool.map(lambda _: client.post("/api/v1/experience/commands", json=cmd), range(8))
        )
    assert all(r.status_code == 200 for r in results)
    commands = client.get("/api/v1/experience/commands").json()["commands"]
    assert len(commands) == 1
    assert client.get("/api/v1/experience/commands").json()["commands"] == commands
    url = "/api/v1/experience/commands/diagnostic-one/ack"
    assert (
        client.post(url, json={"response": {"request_id": "wrong", "type": "state"}}).status_code
        == 422
    )
    assert (
        client.post(
            url,
            json={"response": {"request_id": "diagnostic-one", "type": "state", "state": "ready"}},
        ).status_code
        == 200
    )
    assert client.get("/api/v1/experience/commands").json()["commands"] == []


def test_pause_clears_voice_even_when_stale_meter_arrives(client):
    sid = client.post("/api/v1/sessions", json={"request_id": "pause-meter"}).json()["id"]
    client.post(f"/api/v1/sessions/{sid}/capture-state", json={"state": "paused"})
    assert publish(client, sid, "paused", voice={"level": 100, "clipping": True}).status_code == 200
    assert client.get("/api/v1/experience/public").json()["voice"] is None


def test_fair_timeout_queues_real_reset_without_claiming_completed(client, monkeypatch):
    from app.api import routes_experience

    publish(client)
    client.post(
        "/api/v1/experience/commands",
        json={
            "request_id": "fair-mode",
            "command": "diagnose",
            "mode": "fair",
        },
    )
    now = routes_experience.time.time()
    monkeypatch.setattr(routes_experience.time, "time", lambda: now + 100)
    state = client.get("/api/v1/experience/public").json()
    assert state["state"] != "completed" and state["result"] is None
    # A public read must never schedule an administrative action.
    commands = client.get("/api/v1/experience/commands").json()["commands"]
    assert not any(c["command"] == "reset" for c in commands)
    publish(client)
    commands = client.get("/api/v1/experience/commands").json()["commands"]
    assert sum(c["command"] == "reset" for c in commands) == 1
    client.get("/api/v1/experience/public")
    assert len(client.get("/api/v1/experience/commands").json()["commands"]) == len(commands)


def test_calibration_allowlist_strips_paths_audio_and_text(client):
    response = publish(
        client,
        calibration={
            "status": "ready",
            "device_id": "synthetic",
            "audio": "PRIVATE",
            "transcript": "PRIVATE",
            "path": "/secret",
        },
    )
    assert response.status_code == 200
    snapshot = client.get("/api/v1/experience/public").json()
    assert snapshot["calibration"]["status"] == "ready"
    assert "device_id" not in snapshot["calibration"]
    assert "PRIVATE" not in json.dumps(snapshot)


def test_late_reset_ack_cannot_clear_new_visitor(client):
    from app.database.connection import SessionLocal
    from app.database.models import SessionStatus, StudySession

    first = client.post("/api/v1/sessions", json={"request_id": "late-first"}).json()["id"]
    publish(client, first, "recording")
    client.post(
        "/api/v1/experience/commands",
        json={
            "request_id": "late-reset",
            "command": "reset",
            "session_id": first,
            "confirmed": True,
        },
    )
    with SessionLocal() as db:
        db.get(StudySession, first).status = SessionStatus.error
        db.commit()
    second = client.post("/api/v1/sessions", json={"request_id": "late-second"}).json()["id"]
    assert publish(client, second, "recording").status_code == 200
    ack = client.post(
        "/api/v1/experience/commands/late-reset/ack",
        json={
            "response": {
                "type": "state",
                "request_id": "late-reset",
                "state": "idle",
                "session_id": None,
            }
        },
    )
    assert ack.status_code == 409
    assert client.get("/api/v1/experience/public").json()["session_id"] == second


def test_public_journey_and_diagnostics_have_strict_allowlist(client):
    from app.database.connection import SessionLocal
    from app.database.models import StudySession

    sid = client.post("/api/v1/sessions", json={"request_id": "safe-journey"}).json()["id"]
    with SessionLocal() as db:
        db.get(StudySession, sid).journey_json = json.dumps(
            {
                "capture": {
                    "status": "running",
                    "duration_ms": 0,
                    "provider": "mac_microphone",
                    "is_demo": True,
                    "transcription": "PRIVATE",
                }
            }
        )
        db.commit()
    publish(
        client,
        sid,
        "recording",
        diagnostics=[
            {"component": "microphone", "status": "error", "message": "PRIVATE /path/to/device"}
        ],
    )
    public = client.get("/api/v1/experience/public")
    assert "PRIVATE" not in public.text
    assert "transcription" not in public.json()["journey"][0]


def test_tombstoned_result_is_not_public(client):
    from app.database.connection import SessionLocal
    from app.database.models import SessionStatus, StudySession

    sid = client.post("/api/v1/sessions", json={"request_id": "hidden-deleting"}).json()["id"]
    with SessionLocal() as db:
        row = db.get(StudySession, sid)
        row.status = SessionStatus.completed
        row.transcription = "synthetic"
        row.asr_provider_used = "mock"
        row.topic_provider_used = "mock"
        db.commit()
    assert (
        client.post(
            "/api/v1/experience/bridge",
            json={"session_id": sid, "state": "completed", "is_demo": True},
        ).status_code
        == 200
    )
    with SessionLocal() as db:
        db.get(StudySession, sid).deletion_pending = True
        db.commit()
    response = client.get("/api/v1/experience/public").json()
    assert response["result"] is None

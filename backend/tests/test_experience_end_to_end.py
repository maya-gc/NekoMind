"""Public/touch queue -> actual bridge -> API/SQLite. Synthetic microphone only."""

import json
import time

import pytest

from app.database.connection import SessionLocal
from app.database.operations import Experience
from app.mac.__main__ import DemoRecorder
from app.mac.backend import LocalBackend
from app.mac.bridge import MacBridge


def wait_state(client, bridge, expected, timeout=5):
    deadline = time.monotonic() + timeout
    observed = None
    while time.monotonic() < deadline:
        bridge.tick()
        observed = client.get("/api/v1/experience/public").json()
        if observed["state"] == expected:
            return observed
        time.sleep(0.01)
    pytest.fail(
        f"Expected {expected}; observed state={observed.get('state') if observed else None}"
    )


def send(client, command, rid, sid=None, confirmed=False, mode=None):
    payload = {"command": command, "request_id": rid, "session_id": sid, "confirmed": confirmed}
    if mode:
        payload["mode"] = mode
    response = client.post("/api/v1/experience/commands", json=payload)
    assert response.status_code == 200, response.status_code
    return response


def test_fair_demo_full_queue_pipeline_and_next_visitor(client, tmp_path, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("NEKOMIND_MAC_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    recorder = DemoRecorder(tmp_path / "capture")
    bridge = MacBridge(LocalBackend(client=client), recorder, tmp_path / "journal.db")
    try:
        send(client, "diagnose", "fair-check", mode="fair")
        ready = wait_state(client, bridge, "ready")
        assert ready["diagnostics"]
        assert all(c["status"] in {"ready", "skipped"} for c in ready["diagnostics"])
        send(client, "start", "fair-start")
        # Lost enqueue acknowledgement / double tap repeats the SAME request.
        send(client, "start", "fair-start")
        recording = wait_state(client, bridge, "recording")
        sid = recording["session_id"]
        assert sid and recording["is_demo"]
        assert len(client.get("/api/v1/sessions").json()) == 1
        send(client, "pause", "fair-pause", sid)
        assert wait_state(client, bridge, "paused")["voice"] is None
        send(client, "resume", "fair-resume", sid)
        wait_state(client, bridge, "recording")
        send(client, "finish", "fair-finish", sid)
        complete = wait_state(client, bridge, "completed")
        assert complete["session_id"] == sid
        assert complete["result"]["topics"] and complete["is_demo"] is True
        assert all(step["status"] in {"completed", "skipped"} for step in complete["journey"])
        detail = client.get(f"/api/v1/sessions/{sid}").json()
        assert len(detail["metrics"]) == 6
        send(client, "finish", "fair-finish", sid)
        bridge.tick()
        assert len(client.get(f"/api/v1/sessions/{sid}").json()["metrics"]) == 6
        send(client, "reset", "fair-reset", sid, confirmed=True)
        cleared = wait_state(client, bridge, "idle")
        assert cleared["session_id"] is None and cleared["result"] is None
        assert cleared["journey"] == [] and cleared["voice"] is None
        assert cleared["generation"] > recording["generation"]
        assert not (tmp_path / "capture" / f"capture_{sid}.raw").exists()
        send(client, "diagnose", "next-check")
        wait_state(client, bridge, "ready")
        send(client, "start", "next-start")
        assert wait_state(client, bridge, "recording")["session_id"] != sid
    finally:
        bridge.close()


def test_idle_reset_is_idempotent_without_session(client, tmp_path):
    bridge = MacBridge(
        LocalBackend(client=client), DemoRecorder(tmp_path / "capture"), tmp_path / "journal.db"
    )
    try:
        send(client, "reset", "empty-reset", confirmed=True)
        wait_state(client, bridge, "idle")
        assert bridge.sid is None
        send(client, "reset", "empty-reset", confirmed=True)
        bridge.tick()
        assert client.get("/api/v1/sessions").json() == []
    finally:
        bridge.close()


def test_ready_does_not_expire_while_student_prepares(client):
    assert (
        client.post(
            "/api/v1/experience/bridge", json={"state": "ready", "is_demo": True}
        ).status_code
        == 200
    )
    with SessionLocal() as db:
        row = db.get(Experience, 1)
        state = json.loads(row.payload)
        state.update(
            experience_mode="fair",
            state="ready",
            activity=time.time() - 1000,
        )
        row.payload = json.dumps(state)
        db.commit()

    response = client.post("/api/v1/experience/bridge", json={"state": "ready", "is_demo": True})
    assert response.status_code == 200, response.text
    assert client.get("/api/v1/experience/commands").json()["commands"] == []
    assert client.get("/api/v1/experience/public").json()["state"] == "ready"

    with SessionLocal() as db:
        row = db.get(Experience, 1)
        state = json.loads(row.payload)
        state.update(state="error", activity=time.time() - 1000)
        row.payload = json.dumps(state)
        db.commit()
    assert (
        client.post(
            "/api/v1/experience/bridge", json={"state": "error", "is_demo": True}
        ).status_code
        == 200
    )
    commands = client.get("/api/v1/experience/commands").json()["commands"]
    assert len(commands) == 1 and commands[0]["command"] == "reset"


def test_fair_start_after_long_ready_wait_creates_one_session(client, tmp_path):
    bridge = MacBridge(
        LocalBackend(client=client), DemoRecorder(tmp_path / "capture"), tmp_path / "journal.db"
    )
    try:
        send(client, "diagnose", "long-wait-check", mode="fair")
        wait_state(client, bridge, "ready")
        with SessionLocal() as db:
            row = db.get(Experience, 1)
            state = json.loads(row.payload)
            state["activity"] = time.time() - 1000
            row.payload = json.dumps(state)
            db.commit()
        bridge.tick()
        assert client.get("/api/v1/experience/commands").json()["commands"] == []
        send(client, "start", "long-wait-start")
        assert wait_state(client, bridge, "recording")["session_id"] is not None
        assert len(client.get("/api/v1/sessions").json()) == 1
    finally:
        bridge.close()

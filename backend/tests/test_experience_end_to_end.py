"""Public/touch queue -> actual bridge -> API/SQLite. Synthetic microphone only."""

import time

import pytest

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

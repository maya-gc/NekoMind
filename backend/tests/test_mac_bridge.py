"""Bridge integration with fake microphone/backend, persistent real SQLite journal."""

import importlib
from concurrent.futures import ThreadPoolExecutor

import pytest


class Recorder:
    def __init__(self, path):
        self.path, self.starts, self.stops, self.pauses = path, 0, 0, 0
        self.fail = False

    def start(self, sid):
        self.starts += 1
        if self.fail:
            raise RuntimeError("permission denied")

    def pause(self):
        self.pauses += 1

    def resume(self):
        self.starts += 1

    def finish(self):
        self.stops += 1
        self.path.write_bytes(b"\0\0" * 1600)
        return self.path

    def abort(self):
        self.stops += 1

    def check(self):
        if self.fail:
            raise RuntimeError("device lost")


class Backend:
    def __init__(self):
        self.creates, self.finishes, self.uploads = 0, 0, 0
        self.rows = {}

    def create(self, rid):
        self.creates += 1
        sid = self.creates
        self.rows[sid] = {"id": sid, "status": "recording", "is_demo": True}
        return self.rows[sid]

    def get(self, sid):
        return self.rows[sid]

    def capture_state(self, sid, state, code=None):
        self.rows[sid]["status"] = state
        self.rows[sid]["error_code"] = code
        return self.rows[sid]

    def upload(self, sid, path):
        self.uploads += 1

    def finish(self, sid, rid=None):
        self.finishes += 1
        self.rows[sid].update(
            status="completed",
            transcription="[DEMO]",
            asr_provider="mock",
            topic_provider="mock",
            topics=[{"session_id": sid, "name": "fotossintese"}],
        )
        return self.rows[sid]


def make_bridge(tmp_path, backend=None, recorder=None):
    from app import mac

    assert importlib.util.find_spec(mac.__name__ + ".bridge"), "persistent Mac bridge required"
    from app.mac.bridge import MacBridge

    return MacBridge(
        backend or Backend(),
        recorder or Recorder(tmp_path / "capture.raw"),
        tmp_path / "journal.db",
    )


def command(action, rid, sid=None):
    return {"v": 1, "type": "command", "request_id": rid, "command": action, "session_id": sid}


def test_start_replay_and_concurrent_double_touch(tmp_path):
    b, r = Backend(), Recorder(tmp_path / "audio.raw")
    bridge = make_bridge(tmp_path, b, r)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(bridge.handle, [command("start", "same")] * 2))
    assert responses[0] == responses[1]
    assert r.starts == b.creates == 1
    assert bridge.handle(command("start", "different"))["type"] == "error"
    bridge.close()


def test_pause_resume_finish_replay_and_new_attempt(tmp_path):
    b, r = Backend(), Recorder(tmp_path / "audio.raw")
    bridge = make_bridge(tmp_path, b, r)
    assert bridge.handle(command("start", "s"))["state"] == "recording"
    assert bridge.handle(command("pause", "p", 1))["state"] == "paused"
    bridge.handle(command("pause", "p", 1))
    assert r.pauses == 1
    assert bridge.handle(command("resume", "r", 1))["state"] == "recording"
    bridge.handle(command("finish", "f", 1))
    bridge.wait_for_analysis()
    final = bridge.handle(command("finish", "f", 1))
    assert final["type"] == "result" and final["is_demo"] is True
    assert b.finishes == b.uploads == r.stops == 1
    assert bridge.handle(command("retry", "new", 1))["session_id"] == 2
    bridge.close()


def test_permission_failure_never_acknowledges_recording(tmp_path):
    b, r = Backend(), Recorder(tmp_path / "audio.raw")
    r.fail = True
    bridge = make_bridge(tmp_path, b, r)
    result = bridge.handle(command("start", "s"))
    assert result["type"] == "error"
    assert bridge.handle(command("start", "s")) == result
    assert b.finishes == 0
    bridge.close()


def test_restart_does_not_restart_microphone_or_replay_recording(tmp_path):
    b, r = Backend(), Recorder(tmp_path / "audio.raw")
    bridge = make_bridge(tmp_path, b, r)
    bridge.handle(command("start", "s"))
    bridge.close()
    fresh = make_bridge(tmp_path, b, r)
    assert fresh.handle(command("start", "s"))["type"] == "error"
    assert r.starts == b.creates == 1
    fresh.close()


def test_disconnect_stops_capture_and_allows_retry(tmp_path):
    b, r = Backend(), Recorder(tmp_path / "audio.raw")
    bridge = make_bridge(tmp_path, b, r)
    bridge.handle(command("start", "s"))
    bridge.disconnect()
    assert r.stops == 1
    assert bridge.handle(command("status", "check", 1))["type"] == "error"
    assert bridge.handle(command("retry", "new", 1))["session_id"] == 2
    bridge.close()


def test_request_collision_and_wrong_session_rejected(tmp_path):
    bridge = make_bridge(tmp_path)
    bridge.handle(command("start", "s"))
    assert bridge.handle(command("pause", "s", 1))["code"] == "request_conflict"
    assert bridge.handle(command("finish", "f", 999))["type"] == "error"
    bridge.close()


@pytest.mark.parametrize(
    "change",
    [
        {"status": "processing"},
        {"id": 999},
        {"topics": "invalid"},
        {"is_demo": "false"},
        {"asr_provider": ""},
        {"transcription": ""},
    ],
)
def test_invalid_backend_result_never_completes(tmp_path, change):
    b = Backend()
    finish = b.finish

    def invalid(sid, rid=None):
        finish(sid)
        b.rows[sid].update(change)
        return b.rows[sid]

    b.finish = invalid
    bridge = make_bridge(tmp_path, b)
    bridge.handle(command("start", "s"))
    bridge.handle(command("finish", "f", 1))
    bridge.wait_for_analysis()
    assert bridge.handle(command("finish", "f", 1))["type"] != "result"
    bridge.close()


def test_failed_retry_preserves_previous_completed_session(tmp_path):
    b = Backend()
    bridge = make_bridge(tmp_path, b)
    bridge.handle(command("start", "s"))
    bridge.handle(command("finish", "f", 1))
    bridge.wait_for_analysis()

    def fail_create(rid):
        raise RuntimeError("offline")

    b.create = fail_create
    assert bridge.handle(command("retry", "new", 1))["code"] == "backend_unavailable"
    assert bridge.handle(command("status", "check", 1))["type"] == "result"
    assert b.rows[1]["status"] == "completed"
    bridge.close()


def test_finish_timeout_recovers_via_same_request_without_second_analysis(tmp_path):
    b = Backend()

    def timeout(sid, *args):
        b.finishes += 1
        b.rows[sid]["status"] = "processing"
        raise TimeoutError("response lost")

    b.finish = timeout
    bridge = make_bridge(tmp_path, b)
    bridge.handle(command("start", "s"))
    bridge.handle(command("finish", "f", 1))
    bridge.wait_for_analysis()
    b.rows[1].update(
        status="completed",
        transcription="[DEMO]",
        asr_provider="mock",
        topic_provider="mock",
        topics=[],
    )
    assert bridge.handle(command("finish", "f", 1))["type"] == "result"
    assert b.finishes == 1
    bridge.close()


def test_pause_acknowledges_only_matching_backend_state(tmp_path):
    b = Backend()
    bridge = make_bridge(tmp_path, b)
    bridge.handle(command("start", "s"))
    b.capture_state = lambda *args: {"id": 1, "status": "processing"}
    assert bridge.handle(command("pause", "p", 1))["type"] == "error"
    assert bridge.state != "paused"
    bridge.close()


def test_inflight_finish_recovers_completed_without_reanalysis(tmp_path):
    b = Backend()

    def inflight(sid, rid=None):
        b.finishes += 1
        b.rows[sid]["status"] = "processing"
        return b.rows[sid]

    b.finish = inflight
    bridge = make_bridge(tmp_path, b)
    bridge.handle(command("start", "s"))
    bridge.handle(command("finish", "f", 1))
    bridge.wait_for_analysis()
    assert bridge.handle(command("finish", "f", 1))["state"] == "processing"
    b.rows[1].update(
        status="completed",
        transcription="demo",
        asr_provider="mock",
        topic_provider="mock",
        topics=[],
    )
    assert bridge.handle(command("status", "get", 1))["type"] == "result"
    assert b.finishes == 1
    bridge.close()

"""Bridge integration with fake microphone/backend, persistent real SQLite journal."""

import importlib
from concurrent.futures import ThreadPoolExecutor

import pytest


class Recorder:
    def __init__(self, path):
        self.path, self.starts, self.stops, self.pauses = path, 0, 0, 0
        self.fail = False
        self.probes = 0
        self.calibrations = 0
        self._manifest = {"confirmed_bytes": 0, "chunks": [], "path": str(path)}

    def start(self, sid):
        self.starts += 1
        if self.fail:
            raise RuntimeError("permission denied")
        self.path.write_bytes(b"")

    def pause(self):
        self.pauses += 1

    def resume(self):
        self.starts += 1

    def finish(self):
        self.stops += 1
        self.path.write_bytes(b"\0\0" * 1600)
        self._manifest = {
            "confirmed_bytes": self.path.stat().st_size,
            "chunks": [
                {
                    "sequence": 0,
                    "offset": 0,
                    "byte_size": self.path.stat().st_size,
                    "path": str(self.path),
                }
            ],
            "path": str(self.path),
        }
        return self.path

    def abort(self):
        self.stops += 1

    def check(self):
        if self.fail:
            raise RuntimeError("device lost")

    def probe(self):
        self.probes += 1
        if self.fail:
            return [{"component": "microphone", "status": "error", "message": "missing"}]
        return [{"component": "microphone", "status": "ready", "message": "ok"}]

    def calibrate(self):
        self.calibrations += 1
        if self.fail:
            return {
                "status": "error",
                "device_id": "fake",
                "quality": "unknown",
                "message": "failed",
                "duration_seconds": 1,
                "valid": False,
            }
        return {
            "status": "ready",
            "device_id": "fake",
            "quality": "ok",
            "message": "ok",
            "duration_seconds": 1,
            "valid": True,
        }

    def recovery_manifest(self, sid):
        return dict(self._manifest)

    def recover(self, sid, *, confirmed_bytes=0):
        self.starts += 1
        if not self.path.exists():
            raise RuntimeError("missing")


class Backend:
    def __init__(self):
        self.creates, self.finishes, self.uploads = 0, 0, 0
        self.published, self.acked, self.recoveries, self.cancellations = [], [], [], []
        self.queued_commands = []
        self.uploaded = []
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

    def upload_manifest(self, sid, manifest):
        for chunk in manifest:
            self.uploads += 1
            self.uploaded.append((sid, chunk["sequence"], chunk["byte_size"]))

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

    def publish(self, snapshot):
        self.published.append(snapshot)
        return {"ok": True}

    def commands(self):
        queued, self.queued_commands = self.queued_commands, []
        return {"commands": queued}

    def ack_command(self, rid, response):
        self.acked.append((rid, response))
        return {"acked": True}

    def readiness(self):
        return {
            "components": [
                {"component": "backend", "status": "ready", "message": "ok"},
                {"component": "microphone", "status": "ready", "message": "ok"},
            ]
        }

    def recover(self, sid, action, rid):
        self.recoveries.append((sid, action, rid))
        self.rows[sid]["status"] = "recording" if action == "resume" else "processing"
        return self.rows[sid]

    def cancel(self, sid, *, confirmed=True):
        self.cancellations.append((sid, confirmed))
        self.rows[sid]["status"] = "cancelled"
        return self.rows[sid]

    def delete(self, sid, confirmed=True):
        self.rows.pop(sid, None)
        return {"deleted": True, "session_id": sid}


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


def run_background(bridge):
    bridge.wait_for_operations()


def test_start_requires_successful_preflight_and_then_replays(tmp_path):
    b, r = Backend(), Recorder(tmp_path / "audio.raw")
    bridge = make_bridge(tmp_path, b, r)
    blocked = bridge.handle(command("start", "before-preflight"))
    assert blocked["type"] == "error"

    assert bridge.handle(command("diagnose", "diag"))["state"] == "checking"
    run_background(bridge)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(bridge.handle, [command("start", "same")] * 2))
    assert responses[0] == responses[1]
    assert r.starts == b.creates == 1
    assert b.rows[1]["status"] == "recording"
    assert bridge.handle(command("start", "different"))["type"] == "error"
    bridge.close()


def test_pause_resume_finish_replay_and_new_attempt(tmp_path):
    b, r = Backend(), Recorder(tmp_path / "audio.raw")
    bridge = make_bridge(tmp_path, b, r)
    bridge.handle(command("diagnose", "diag"))
    run_background(bridge)
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
    bridge.handle(command("diagnose", "diag"))
    run_background(bridge)
    result = bridge.handle(command("start", "s"))
    assert result["type"] == "error"
    assert bridge.handle(command("start", "s")) == result
    assert b.finishes == 0
    bridge.close()


def test_restart_does_not_restart_microphone_or_replay_recording(tmp_path):
    b, r = Backend(), Recorder(tmp_path / "audio.raw")
    bridge = make_bridge(tmp_path, b, r)
    bridge.handle(command("diagnose", "diag"))
    run_background(bridge)
    bridge.handle(command("start", "s"))
    bridge.close()
    fresh = make_bridge(tmp_path, b, r)
    assert fresh.handle(command("start", "s"))["type"] == "error"
    assert r.starts == b.creates == 1
    fresh.close()


def test_disconnect_stops_capture_and_allows_retry(tmp_path):
    b, r = Backend(), Recorder(tmp_path / "audio.raw")
    bridge = make_bridge(tmp_path, b, r)
    bridge.handle(command("diagnose", "diag"))
    run_background(bridge)
    bridge.handle(command("start", "s"))
    bridge.disconnect()
    assert r.stops == 1
    status = bridge.handle(command("status", "check", 1))
    assert status["type"] == "error" and status["state"] == "recovery"
    assert bridge.handle(command("retry", "new", 1))["session_id"] == 2
    bridge.close()


def test_request_collision_and_wrong_session_rejected(tmp_path):
    bridge = make_bridge(tmp_path)
    bridge.handle(command("diagnose", "diag"))
    run_background(bridge)
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
    bridge.handle(command("diagnose", "diag"))
    run_background(bridge)
    bridge.handle(command("start", "s"))
    bridge.handle(command("finish", "f", 1))
    bridge.wait_for_analysis()
    assert bridge.handle(command("finish", "f", 1))["type"] != "result"
    bridge.close()


def test_failed_retry_preserves_previous_completed_session(tmp_path):
    b = Backend()
    bridge = make_bridge(tmp_path, b)
    bridge.handle(command("diagnose", "diag"))
    run_background(bridge)
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
    bridge.handle(command("diagnose", "diag"))
    run_background(bridge)
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
    bridge.handle(command("diagnose", "diag"))
    run_background(bridge)
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
    bridge.handle(command("diagnose", "diag"))
    run_background(bridge)
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


@pytest.mark.parametrize("action", ["diagnose", "calibrate"])
def test_operator_diagnostics_are_explicit_and_do_not_open_microphone(tmp_path, action):
    b, r = Backend(), Recorder(tmp_path / "audio.raw")
    bridge = make_bridge(tmp_path, b, r)

    response = bridge.handle(command(action, f"{action}-1"))

    assert response["state"] == "checking"
    assert "diagnostics" not in response
    run_background(bridge)
    assert bridge.diagnostics[0]["status"] == "ready"
    if action == "calibrate":
        assert bridge.calibration["duration_seconds"] == 1
        assert bridge.calibration["valid"] is True
    assert r.starts == 0
    bridge.close()


def test_recover_resume_reopens_capture_only_for_explicit_command(tmp_path):
    b, r = Backend(), Recorder(tmp_path / "audio.raw")
    bridge = make_bridge(tmp_path, b, r)
    bridge.handle(command("diagnose", "diag"))
    run_background(bridge)
    bridge.handle(command("start", "s"))
    bridge.disconnect()

    fresh = make_bridge(tmp_path, b, r)
    assert fresh.handle(command("status", "st", 1))["state"] == "recovery"
    assert r.starts == 1

    recovered = fresh.handle(command("recover", "rec", 1))

    assert recovered["state"] == "recording"
    assert r.starts == 2
    assert b.rows[1]["status"] == "recording"
    fresh.close()


@pytest.mark.parametrize("action", ["discard", "cancel", "reset"])
def test_destructive_bridge_commands_are_idempotent_intentions(tmp_path, action):
    b, r = Backend(), Recorder(tmp_path / "audio.raw")
    bridge = make_bridge(tmp_path, b, r)
    bridge.handle(command("diagnose", "diag"))
    run_background(bridge)
    bridge.handle(command("start", "s"))
    sid = bridge.sid

    first = bridge.handle(command(action, f"{action}-1", sid))
    second = bridge.handle(command(action, f"{action}-1", sid))

    assert first == second
    assert first["state"] == "idle"
    assert r.stops >= 1
    bridge.close()


def test_tick_publishes_snapshot_polls_commands_and_acks(tmp_path):
    b, r = Backend(), Recorder(tmp_path / "audio.raw")
    b.queued_commands.append(command("diagnose", "cmd-1"))
    bridge = make_bridge(tmp_path, b, r)

    bridge.tick()
    bridge.wait_for_operations()

    assert b.published and b.published[-1]["state"] == "idle"
    assert b.published[-1]["diagnostics"] == []
    assert b.acked and b.acked[-1][0] == "cmd-1"
    assert b.acked[-1][1]["state"] in {"checking", "ready"}
    assert "diagnostics" not in b.acked[-1][1]
    run_background(bridge)
    bridge.close()


def test_incremental_upload_cursor_survives_restart_and_deduplicates(tmp_path):
    b, r = Backend(), Recorder(tmp_path / "audio.raw")
    r.path.write_bytes(b"a" * 600)
    r._manifest = {
        "confirmed_bytes": 600,
        "chunks": [
            {"sequence": 0, "offset": 0, "byte_size": 512, "path": str(r.path)},
            {"sequence": 1, "offset": 512, "byte_size": 88, "path": str(r.path)},
        ],
        "path": str(r.path),
    }
    bridge = make_bridge(tmp_path, b, r)
    bridge.handle(command("diagnose", "diag"))
    run_background(bridge)
    bridge.handle(command("start", "s"))

    bridge.tick(force=True)
    bridge.wait_for_operations()
    bridge.close()
    fresh = make_bridge(tmp_path, b, r)
    fresh.tick(force=True)
    fresh.wait_for_operations()

    assert b.uploaded == [(1, 0, 512), (1, 1, 88)]
    fresh.close()


def test_recover_analyze_uses_backend_without_reopening_microphone(tmp_path):
    b, r = Backend(), Recorder(tmp_path / "audio.raw")
    bridge = make_bridge(tmp_path, b, r)
    bridge.sid, bridge.state = 3, "processing"
    b.rows[3] = {"id": 3, "status": "processing", "is_demo": True}
    response = bridge.handle(command("recover", "recover-analysis", 3))

    assert response["state"] == "processing"
    bridge.future.result(timeout=2)
    assert r.starts == 0
    assert b.recoveries == [(3, "analyze", "recover-analysis")]
    bridge.close()


def test_restart_during_transcription_recovers_analysis_without_microphone(tmp_path):
    b, r = Backend(), Recorder(tmp_path / "audio.raw")
    bridge = make_bridge(tmp_path, b, r)
    bridge.sid, bridge.state = 3, "recovery"
    b.rows[3] = {
        "id": 3,
        "status": "recovery",
        "is_demo": True,
        "journey": {"transcription": {"status": "running"}},
    }
    response = bridge.handle(command("recover", "recover-crash", 3))
    assert response["state"] == "processing"
    bridge.future.result(timeout=2)
    assert r.starts == 0
    assert b.recoveries == [(3, "analyze", "recover-crash")]
    bridge.close()


def test_retry_cannot_bypass_missing_readiness(tmp_path):
    b, r = Backend(), Recorder(tmp_path / "audio.raw")
    bridge = make_bridge(tmp_path, b, r)
    response = bridge.handle(command("retry", "retry-without-diagnostics", None))
    assert response["type"] == "error"
    assert b.creates == r.starts == 0
    bridge.close()


class ListManifestRecorder(Recorder):
    def recovery_manifest(self, sid):
        return list(self._manifest.get("chunks", []))


def test_recovery_manifest_accepts_list_contract_without_tick_crash(tmp_path):
    b, r = Backend(), ListManifestRecorder(tmp_path / "audio.raw")
    r.path.write_bytes(b"a" * 600)
    r._manifest = {
        "confirmed_bytes": 600,
        "chunks": [
            {"sequence": 0, "offset": 0, "byte_size": 512, "path": str(r.path)},
            {"sequence": 1, "offset": 512, "byte_size": 88, "path": str(r.path)},
        ],
        "path": str(r.path),
    }
    bridge = make_bridge(tmp_path, b, r)
    bridge.handle(command("diagnose", "diag"))
    run_background(bridge)
    bridge.handle(command("start", "s"))

    bridge.tick(force=True)
    bridge.wait_for_operations()

    assert b.uploaded == [(1, 0, 512), (1, 1, 88)]
    bridge.close()


def test_tick_worker_keeps_capture_running_when_backend_ops_are_offline(tmp_path):
    class OfflineBackend(Backend):
        def publish(self, snapshot):
            raise TimeoutError("offline")

    b, r = OfflineBackend(), Recorder(tmp_path / "audio.raw")
    bridge = make_bridge(tmp_path, b, r)
    bridge.handle(command("diagnose", "diag"))
    run_background(bridge)
    bridge.handle(command("start", "s"))

    bridge.tick(force=True)
    bridge.wait_for_operations()

    assert bridge.state == "recording"
    assert r.starts == 1
    bridge.close()


@pytest.mark.parametrize("action", ["diagnose", "calibrate"])
def test_diagnose_and_calibrate_are_blocked_during_capture_and_processing(tmp_path, action):
    b, r = Backend(), Recorder(tmp_path / "audio.raw")
    bridge = make_bridge(tmp_path, b, r)
    bridge.handle(command("diagnose", "diag"))
    run_background(bridge)
    bridge.handle(command("start", "s"))
    assert bridge.handle(command(action, f"busy-{action}"))["code"] == "invalid_state"
    bridge.handle(command("finish", "f", 1))
    assert bridge.handle(command(action, f"processing-{action}"))["code"] == "invalid_state"
    bridge.wait_for_analysis()
    bridge.close()


def test_reset_completed_keeps_backend_result_and_does_not_cancel_completed_session(tmp_path):
    b, r = Backend(), Recorder(tmp_path / "audio.raw")
    bridge = make_bridge(tmp_path, b, r)
    bridge.handle(command("diagnose", "diag"))
    run_background(bridge)
    bridge.handle(command("start", "s"))
    bridge.handle(command("finish", "f", 1))
    bridge.wait_for_analysis()

    response = bridge.handle(command("reset", "reset", 1))

    assert response["state"] == "idle"
    assert b.rows[1]["status"] == "completed"
    assert b.cancellations == []
    bridge.close()


def test_cancel_uses_backend_cancel_not_fake_idle_for_processing(tmp_path):
    b, r = Backend(), Recorder(tmp_path / "audio.raw")
    bridge = make_bridge(tmp_path, b, r)
    bridge.sid, bridge.state = 9, "processing"
    b.rows[9] = {"id": 9, "status": "processing", "is_demo": True}

    response = bridge.handle(command("cancel", "cancel-processing", 9))

    assert response["state"] == "idle" and response["session_id"] is None
    assert b.cancellations == [(9, True)]
    assert b.rows[9]["status"] == "cancelled"
    bridge.close()

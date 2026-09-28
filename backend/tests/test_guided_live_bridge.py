from time import monotonic

from app.mac.bridge import MacBridge


class FakeRecorder:
    partial_sink = None

    def __init__(self):
        self.quality = "ok"

    def voice(self):
        return {"level": 25, "clipping": False, "quality": self.quality}

    def abort(self):
        pass


class FakeBackend:
    def capture_state(self, *args):
        return {"status": "error"}


def test_live_match_requires_current_session_and_good_capture(tmp_path):
    recorder = FakeRecorder()
    bridge = MacBridge(FakeBackend(), recorder, tmp_path / "journal.db")
    try:
        assert bridge.partial is None
        bridge._start_partials()  # no reference: zero ASR work
        assert bridge.partial is None
        bridge.state, bridge.sid, bridge.demo = "recording", 42, False
        bridge.epoch, bridge.event_rid = 1, "c2-test-1"
        bridge.guided_started_at = monotonic()
        bridge.guided_snapshot = {
            "text": "Plantas usam luz solar e agua.",
            "points": ["Plantas usam luz solar e agua."],
        }
        bridge._on_partial(1, 41, "Plantas usam luz solar e agua.", 0.1)
        assert bridge.live_summary is None
        bridge._on_partial(1, 42, "Plantas usam luz solar e agua.", 0.1)
        assert bridge.live_summary["status"] == "covered"
        assert bridge.live_summary["expression"] == "happy"
        assert next(bridge.drain_events())["type"] == "content"
        recorder.quality = "low"
        bridge._on_partial(1, 42, "Plantas nao usam luz solar e agua.", 0.1)
        assert bridge.live_summary["expression"] == "happy"
        recorder.quality = "ok"
        bridge._on_partial(1, 42, None, None)
        assert bridge.live_summary["status"] == "unavailable"
    finally:
        bridge.close()

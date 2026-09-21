"""Strict wire parser and real pseudo-terminal transport, no physical ESP32."""

import os
import pty
import threading
import time

import pytest

from app.mac.backend import LocalBackend
from app.mac.protocol import decode_line, encode_line


@pytest.mark.parametrize(
    "raw", [b"{}\n", b"[]\n", b'{"v":1,"v":1}\n', b"x" * 4097 + b"\n", b'{"v":1}', b"\xff\n"]
)
def test_invalid_frames(raw):
    with pytest.raises(ValueError):
        decode_line(raw)


def test_round_trip():
    cmd = {
        "v": 1,
        "type": "command",
        "request_id": "boot-1",
        "command": "diagnose",
        "session_id": None,
    }
    assert decode_line(encode_line(cmd)) == cmd


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "http://10.0.0.1",
        "http://127.0.0.1@evil.example",
        "http://user:pass@localhost",
    ],
)
def test_bridge_refuses_remote_backend(url):
    with pytest.raises(ValueError):
        LocalBackend(url)


def test_serial_partial_frames_and_disconnect_watchdog():
    import importlib

    assert importlib.util.find_spec("app.mac.serial_loop"), "bounded serial loop required"
    import serial

    from app.mac.serial_loop import run_serial

    master, slave = pty.openpty()
    stop = threading.Event()

    class Bridge:
        def __init__(self):
            self.calls, self.disconnections, self.connected, self.disconnected_marks = [], 0, 0, 0

        def handle(self, msg):
            self.calls.append(msg)
            return {
                "v": 1,
                "type": "state",
                "request_id": msg["request_id"],
                "session_id": None,
                "state": "idle",
                "is_demo": True,
            }

        def check_capture(self):
            pass

        def disconnect(self):
            self.disconnections += 1

        def mark_serial_connected(self):
            self.connected += 1

        def mark_serial_disconnected(self):
            self.disconnected_marks += 1

        def drain_events(self):
            return []

    bridge = Bridge()
    with serial.Serial(os.ttyname(slave), 115200, timeout=0.02) as port:
        thread = threading.Thread(
            target=run_serial, args=(port, bridge, stop), kwargs={"heartbeat_timeout": 0.15}
        )
        thread.start()
        os.write(master, b'{"v":1,"type":"command",')
        time.sleep(0.04)
        os.write(master, b'"request_id":"h1","command":"status","session_id":null}\n')
        time.sleep(0.1)
        assert len(bridge.calls) == 1
        assert bridge.connected == 1
        time.sleep(0.2)
        stop.set()
        thread.join(1)
        assert not thread.is_alive() and bridge.disconnections >= 1
        assert bridge.disconnected_marks >= 1
    os.close(master)
    os.close(slave)


def test_slow_capture_ack_does_not_trigger_immediate_disconnect():
    from app.mac.serial_loop import run_serial
    import serial

    master, slave = pty.openpty()
    stop = threading.Event()

    class SlowBridge:
        disconnections = 0

        def handle(self, msg):
            time.sleep(0.15)  # permissao/dispositivo podem bloquear o inicio
            stop.set()
            return {
                "v": 1,
                "type": "state",
                "request_id": msg["request_id"],
                "session_id": 1,
                "state": "recording",
                "is_demo": True,
            }

        def check_capture(self):
            pass

        def drain_events(self):
            return []

        def disconnect(self):
            self.disconnections += 1

    bridge = SlowBridge()
    try:
        with serial.Serial(os.ttyname(slave), 115200, timeout=0.02) as port:
            thread = threading.Thread(
                target=run_serial, args=(port, bridge, stop),
                kwargs={"heartbeat_timeout": 0.06},
            )
            thread.start()
            os.write(master, encode_line({
                "v": 1, "type": "command", "request_id": "slow-1",
                "command": "start", "session_id": None,
            }))
            thread.join(2)
            assert not thread.is_alive()
            assert bridge.disconnections == 1  # somente o teardown, nao o watchdog
    finally:
        os.close(master)
        os.close(slave)


def test_result_rejects_boolean_topic_session_id():
    from app.mac.protocol import validate_result

    row = {
        "id": 1,
        "status": "completed",
        "is_demo": True,
        "asr_provider": "mock",
        "topic_provider": "mock",
        "transcription": "demo",
        "topics": [{"session_id": True, "name": "demo"}],
    }
    with pytest.raises(ValueError):
        validate_result(row, 1)


@pytest.mark.parametrize("version", ["true", "1.0"])
def test_command_version_requires_integer(version):
    raw = ('{"v":' + version + ',"type":"command","request_id":"s","command":"start"}\n').encode()
    with pytest.raises(ValueError):
        decode_line(raw)


class _ResponseClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, path, **kwargs):
        import httpx

        self.calls.append((method, path, kwargs))
        payload = self.responses.pop(0)
        return httpx.Response(
            200, json=payload, request=httpx.Request(method, "http://test" + path)
        )

    def close(self):
        pass


def test_local_backend_adds_compact_trend_text_for_confirmed_completed_subject():
    client = _ResponseClient(
        [
            {
                "id": 7,
                "status": "completed",
                "is_demo": True,
                "subject": "Fotossintese",
                "subject_confirmed": True,
                "metric_method_version": "heuristic-v2",
                "asr_provider_used": "mock",
                "topic_provider_used": "mock",
            },
            {
                "subject": "Fotossintese",
                "method_version": "heuristic-v2",
                "trend": {
                    "duration_seconds_delta": 12,
                    "clarity_score_delta": -0.5,
                    "topic_count_delta": 2,
                },
            },
        ]
    )
    backend = LocalBackend(client=client)

    row = backend.get(7)

    assert row["trend_text"] == "duracao +12s; clareza -0.5; topicos +2"
    assert client.calls[1][1] == "/api/v1/history/subjects/Fotossintese"
    assert client.calls[1][2]["params"] == {"method_version": "heuristic-v2"}


def test_result_rejects_deleted_or_deletion_pending_session():
    from app.mac.protocol import validate_result

    row = {
        "id": 1,
        "status": "completed",
        "is_demo": True,
        "asr_provider": "mock",
        "topic_provider": "mock",
        "transcription": "demo",
        "topics": [],
        "deletion_pending": True,
    }
    with pytest.raises(ValueError):
        validate_result(row, 1)

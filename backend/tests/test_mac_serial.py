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
        "command": "start",
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
            self.calls, self.disconnections = [], 0

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
        time.sleep(0.2)
        stop.set()
        thread.join(1)
        assert not thread.is_alive() and bridge.disconnections >= 1
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

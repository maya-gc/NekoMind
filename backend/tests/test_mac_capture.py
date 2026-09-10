"""No real microphone is opened by these tests."""

import importlib

import pytest

from app import mac


class Stream:
    def __init__(self, **kwargs):
        self.callback = kwargs["callback"]
        self.active = False
        self.closed = False

    def start(self):
        self.active = True
        self.callback(b"\x01\x00" * 480, 480, None, False)

    def stop(self):
        self.active = False

    def close(self):
        self.closed = True


def recorder(tmp_path, factory=Stream):
    assert importlib.util.find_spec(mac.__name__ + ".capture"), "Mac stream lifecycle required"
    from app.mac.capture import MacRecorder

    return MacRecorder(tmp_path, stream_factory=factory)


def test_pause_closes_device_resume_preserves_audio(tmp_path):
    r = recorder(tmp_path)
    r.start(1)
    first = r.stream
    r.pause()
    assert first.closed and not first.active
    r.resume()
    second = r.stream
    path = r.finish()
    assert second.closed
    assert path.read_bytes() == b"\x01\x00" * 960


def test_open_failure_cleans_writer_and_stream(tmp_path):
    class Broken(Stream):
        def start(self):
            raise RuntimeError("permission")

    r = recorder(tmp_path, Broken)
    with pytest.raises(RuntimeError):
        r.start(1)
    r.abort()
    assert r.stream is None


def test_callback_error_propagates_to_controller(tmp_path):
    r = recorder(tmp_path)
    r.start(1)
    r.stream.callback(b"", 0, None, True)
    with pytest.raises(RuntimeError, match="capture"):
        r.check()
    r.abort()


def test_disappeared_device_is_not_recording(tmp_path):
    r = recorder(tmp_path)
    r.start(1)
    r.stream.active = False
    with pytest.raises(RuntimeError):
        r.check()
    r.abort()


def test_writer_timeout_cannot_overlap_next_capture(tmp_path):
    from queue import Queue

    class StuckWriter:
        def is_alive(self):
            return True

        def join(self, timeout):
            pass

    r = recorder(tmp_path)
    stuck = StuckWriter()
    r.writer, r.queue = stuck, Queue()
    r._close_writer()
    assert r.writer is stuck
    with pytest.raises(RuntimeError, match="capture_already_active"):
        r.start(2)

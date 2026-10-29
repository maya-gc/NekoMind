"""No real microphone is opened by these tests."""

import importlib
import os

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


def test_recorder_confirms_complete_512k_chunks_and_final_remainder(tmp_path):
    r = recorder(tmp_path)
    r.start(7)
    chunk = b"\x02\x00" * (512 * 1024 // 2)
    r.stream.callback(chunk, len(chunk) // 2, None, False)
    r.stream.callback(b"\x03\x00" * 10, 10, None, False)

    path = r.finish()

    assert path.read_bytes() == b"\x01\x00" * 480 + chunk + b"\x03\x00" * 10
    manifest = r.confirmed_chunks()
    assert manifest == [{"sequence": 0, "offset": 0, "byte_size": 512 * 1024, "path": str(path)}]
    assert r.final_remainder() == {
        "sequence": 1,
        "offset": 512 * 1024,
        "byte_size": 960 + 20,
        "path": str(path),
    }


def test_recorder_recovery_appends_after_confirmed_cursor(tmp_path):
    r = recorder(tmp_path)
    r.start(9)
    r.stream.callback(b"\x04\x00" * (512 * 1024 // 2), 512 * 1024 // 2, None, False)
    r.finish()

    recovered = recorder(tmp_path)
    recovered.recover(9, confirmed_bytes=512 * 1024)
    recovered.stream.callback(b"\x05\x00" * 10, 10, None, False)
    path = recovered.finish()

    assert path.stat().st_size == 512 * 1024 + 960 + 20
    with path.open("rb") as handle:
        handle.seek(512 * 1024 + 960)
        assert handle.read() == b"\x05\x00" * 10


def test_writer_fsyncs_confirmed_chunks(tmp_path, monkeypatch):
    calls = []
    real_fsync = os.fsync

    def tracked(fd):
        calls.append(fd)
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", tracked)
    r = recorder(tmp_path)
    r.start(11)
    r.stream.callback(b"\x06\x00" * (512 * 1024 // 2), 512 * 1024 // 2, None, False)
    r.finish()

    assert calls, "raw chunks must be fsynced before they are confirmed"


def test_recovery_manifest_survives_recorder_restart_without_opening_microphone(tmp_path):
    r = recorder(tmp_path)
    r.start(21)
    r.stream.callback(b"\x07\x00" * (512 * 1024 // 2), 512 * 1024 // 2, None, False)
    path = r.finish()

    fresh = recorder(tmp_path)

    assert fresh.recovery_manifest(21) == {
        "confirmed_bytes": 512 * 1024,
        "chunks": [{"sequence": 0, "offset": 0, "byte_size": 512 * 1024, "path": str(path)}],
        "path": str(path),
    }
    assert fresh.stream is None


def test_recover_refuses_cursor_before_durable_manifest(tmp_path):
    r = recorder(tmp_path)
    r.start(22)
    r.stream.callback(b"\x08\x00" * (512 * 1024 // 2), 512 * 1024 // 2, None, False)
    r.finish()

    fresh = recorder(tmp_path)
    with pytest.raises(RuntimeError, match="capture_invalid_cursor"):
        fresh.recover(22, confirmed_bytes=0)


def test_recovery_manifest_rejects_external_traversal_symlink_and_missing_chunk_file(tmp_path):
    import json

    r = recorder(tmp_path)
    raw_path = tmp_path / "capture_24.raw"
    manifest_path = tmp_path / "capture_24.manifest.json"
    chunk = {"sequence": 0, "offset": 0, "byte_size": 512 * 1024, "path": str(raw_path)}

    manifest_path.write_text(
        json.dumps(
            {
                "version": 1,
                "chunk_bytes": 512 * 1024,
                "path": str(tmp_path / ".." / "capture_24.raw"),
                "confirmed_chunks": [chunk],
            }
        )
    )
    with pytest.raises(RuntimeError, match="capture_recovery_missing"):
        r.recovery_manifest(24)

    external = tmp_path.parent / "external.raw"
    manifest_path.write_text(
        json.dumps(
            {
                "version": 1,
                "chunk_bytes": 512 * 1024,
                "path": str(external),
                "confirmed_chunks": [chunk],
            }
        )
    )
    with pytest.raises(RuntimeError, match="capture_recovery_missing"):
        r.recovery_manifest(24)

    raw_path.symlink_to(external)
    manifest_path.write_text(
        json.dumps(
            {
                "version": 1,
                "chunk_bytes": 512 * 1024,
                "path": str(raw_path),
                "confirmed_chunks": [chunk],
            }
        )
    )
    with pytest.raises(RuntimeError, match="capture_recovery_missing"):
        r.recovery_manifest(24)

    raw_path.unlink()
    manifest_path.write_text(
        json.dumps(
            {
                "version": 1,
                "chunk_bytes": 512 * 1024,
                "path": str(raw_path),
                "confirmed_chunks": [chunk],
            }
        )
    )
    with pytest.raises(RuntimeError, match="capture_recovery_missing"):
        r.recovery_manifest(24)


def test_voice_is_only_reported_while_recording(tmp_path):
    r = recorder(tmp_path)

    assert r.voice() is None
    r.start(23)
    assert r.voice() == {"level": 0, "clipping": False, "quality": "unknown"}
    r.stream.callback(b"\xff\x7f" * 480, 480, None, False)
    assert r.voice() == {"level": 100, "clipping": True, "quality": "clipping"}
    r.pause()
    assert r.voice() is None
    r.resume()
    r.finish()
    assert r.voice() is None

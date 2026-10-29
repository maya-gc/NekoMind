"""Calibration and device probing use fake PortAudio; no real microphone opens."""

import struct

from app.mac.capture import MacRecorder


class DeviceInfo:
    @staticmethod
    def query_devices(device=None, kind=None):
        assert kind == "input"
        return {
            "name": "Unit Test Mic",
            "hostapi": 2,
            "index": 4,
            "max_input_channels": 1,
            "default_samplerate": 16000,
        }

    @staticmethod
    def check_input_settings(**kwargs):
        assert kwargs["samplerate"] == 16000
        assert kwargs["channels"] == 1
        assert kwargs["dtype"] == "int16"


class ProbeStream:
    def __init__(self, **kwargs):
        self.callback = kwargs["callback"]
        self.active = False
        self.closed = False

    def start(self):
        self.active = True
        self.callback(b"\0\0" * 480, 480, None, False)

    def stop(self):
        self.active = False

    def close(self):
        self.closed = True


class SpeechStream(ProbeStream):
    def start(self):
        self.active = True
        self.callback(struct.pack("<h", 4000) * 1600, 1600, None, False)


class SpeechDetector:
    def is_speech(self, frame, rate):
        assert rate == 16000
        return any(frame)


def test_probe_reports_real_components_with_stable_device_fingerprint(tmp_path):
    recorder = MacRecorder(
        tmp_path,
        stream_factory=ProbeStream,
        device_api=DeviceInfo,
    )

    report = recorder.probe()

    assert report == [
        {
            "component": "microphone",
            "status": "ready",
            "message": "Unit Test Mic",
        },
        {
            "component": "permission",
            "status": "ready",
            "message": "Input settings accepted",
        },
        {
            "component": "capture",
            "status": "ready",
            "message": "Short input probe captured audio",
        },
    ]


def test_calibrate_uses_vad_quality_and_removes_raw_sample(tmp_path):
    recorder = MacRecorder(
        tmp_path,
        stream_factory=SpeechStream,
        device_api=DeviceInfo,
    )

    result = recorder.calibrate(duration_seconds=0.03, detector=SpeechDetector())

    assert result["status"] == "ready"
    assert result["device_id"] == "input:2:4:Unit Test Mic:16000"
    assert result["quality"] == "ok"
    assert result["valid"] is True
    assert result["duration_seconds"] > 0
    assert not list(tmp_path.glob("*calibration*.raw"))


def test_calibrate_waits_for_the_requested_capture_window(tmp_path, monkeypatch):
    waits = []
    monkeypatch.setattr("app.mac.capture.time.sleep", waits.append)
    recorder = MacRecorder(
        tmp_path,
        stream_factory=SpeechStream,
        device_api=DeviceInfo,
    )

    recorder.calibrate(duration_seconds=3.0, detector=SpeechDetector())

    assert waits == [3.0]


def test_calibrate_creates_capture_directory_on_first_use(tmp_path):
    capture_dir = tmp_path / "capture"
    recorder = MacRecorder(
        capture_dir,
        stream_factory=SpeechStream,
        device_api=DeviceInfo,
    )

    result = recorder.calibrate(duration_seconds=0, detector=SpeechDetector())

    assert result["status"] == "ready"
    assert result["valid"] is True
    assert capture_dir.is_dir()


def test_calibrate_rejects_no_speech_without_treating_level_as_voice(tmp_path):
    recorder = MacRecorder(
        tmp_path,
        stream_factory=ProbeStream,
        device_api=DeviceInfo,
    )

    result = recorder.calibrate(duration_seconds=0.03, detector=SpeechDetector())

    assert result["status"] == "error"
    assert result["quality"] == "no_speech"
    assert result["valid"] is False

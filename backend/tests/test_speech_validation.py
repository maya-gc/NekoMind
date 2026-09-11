"""VAD boundaries: classifier doubles for speech; real WebRTC for silence/noise."""

import random
import struct
import wave

import pytest

from app.services import audio_processing


def wav_file(tmp_path, data, rate=16000, channels=1, width=2):
    path = tmp_path / "test.wav"
    with wave.open(str(path), "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(width)
        out.setframerate(rate)
        out.writeframes(data)
    return path


def validate(path, **kwargs):
    assert hasattr(audio_processing, "validate_speech"), "real audio must pass a speech gate"
    return audio_processing.validate_speech(path, **kwargs)


@pytest.mark.parametrize("data", [b"", b"\0\0" * 32000], ids=["empty", "silence"])
def test_empty_and_silence_rejected(tmp_path, data):
    with pytest.raises(ValueError, match="audio_empty|audio_low|no_speech"):
        validate(wav_file(tmp_path, data))


def test_missing_and_invalid_audio(tmp_path):
    with pytest.raises(ValueError, match="audio_missing"):
        validate(None)
    path = tmp_path / "invalid.wav"
    path.write_bytes(b"invalid wav")
    with pytest.raises(ValueError, match="audio_invalid"):
        validate(path)


def test_white_noise_rejected(tmp_path):
    rng = random.Random(4)
    pcm = b"".join(struct.pack("<h", rng.randint(-500, 500)) for _ in range(32000))
    with pytest.raises(ValueError, match="no_speech"):
        validate(wav_file(tmp_path, pcm))


@pytest.mark.parametrize("amplitude", [20, 300, 5000])
def test_speech_gate_uses_classifier_not_volume_and_allows_pauses(tmp_path, amplitude):
    # The double isolates aggregation policy. It is not acoustic calibration.
    class SpeechDetector:
        def is_speech(self, frame, rate):
            assert len(frame) == 960 and rate == 16000
            return any(frame)

    pcm = b"\0\0" * 48000 + struct.pack("<h", amplitude) * 9600 + b"\0\0" * 48000
    report = validate(wav_file(tmp_path, pcm), detector=SpeechDetector())
    assert report["speech_seconds"] == pytest.approx(0.6)


def test_truncated_wav_rejected(tmp_path):
    path = wav_file(tmp_path, b"\0\0" * 16000)
    path.write_bytes(path.read_bytes()[:-100])
    with pytest.raises(ValueError, match="audio_invalid"):
        validate(path)


def test_stereo_not_silently_reinterpreted(tmp_path):
    with pytest.raises(ValueError, match="audio_invalid"):
        validate(wav_file(tmp_path, b"\0\0" * 16000, channels=2))


def test_audio_quality_reports_clipping_low_level_and_noise(tmp_path):
    from app.services.audio_quality import assess_audio_quality

    clipped = wav_file(tmp_path, struct.pack("<h", 32767) * 16000)
    assert assess_audio_quality(clipped)["quality"] == "clipping"

    low = wav_file(tmp_path, struct.pack("<h", 3) * 16000)
    assert assess_audio_quality(low)["quality"] == "low"

    rng = random.Random(12)
    noisy = wav_file(
        tmp_path, b"".join(struct.pack("<h", rng.randint(-28000, 28000)) for _ in range(16000))
    )
    assert assess_audio_quality(noisy)["quality"] == "noise"


def test_audio_quality_streams_pcm_without_materializing_sample_list(tmp_path, monkeypatch):
    from app.services import audio_quality

    path = wav_file(tmp_path, struct.pack("<h", 400) * 16000)

    def fail_list(*args, **kwargs):
        raise AssertionError("quality must not build a giant Python list of PCM samples")

    monkeypatch.setattr(audio_quality, "list", fail_list, raising=False)

    assert audio_quality.assess_audio_quality(path)["quality"] == "ok"

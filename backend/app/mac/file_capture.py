"""Microphone stand-in that replays WAV files as the student's speech.

Used by the automated pipeline (``app.devtools.pipeline``) and by
``python -m app.mac --audio-file``. Each started session consumes the next
file of the list (the last one repeats). Audio is converted to the bridge's
fixed format: 16 kHz, mono, PCM 16-bit little endian.
"""

from __future__ import annotations

import wave
from array import array
from pathlib import Path

RATE = 16000


def wav_to_pcm16k(path: Path) -> bytes:
    """Read a PCM WAV and return 16 kHz mono s16le bytes (linear resampling)."""
    with wave.open(str(path), "rb") as wav:
        channels, width, rate = wav.getnchannels(), wav.getsampwidth(), wav.getframerate()
        frames = wav.readframes(wav.getnframes())
    if width != 2:
        raise ValueError("Use WAV PCM de 16 bits")
    samples = array("h")
    samples.frombytes(frames)
    if channels > 1:
        mono = array("h", [0]) * (len(samples) // channels)
        for i in range(len(mono)):
            block = samples[i * channels : (i + 1) * channels]
            mono[i] = int(sum(block) / channels)
        samples = mono
    if rate != RATE and samples:
        ratio = rate / RATE
        size = int(len(samples) / ratio)
        out = array("h", [0]) * size
        last = len(samples) - 1
        for i in range(size):
            pos = i * ratio
            left = int(pos)
            right = min(left + 1, last)
            frac = pos - left
            out[i] = int(samples[left] * (1 - frac) + samples[right] * frac)
        samples = out
    return samples.tobytes()


class FileRecorder:
    """Same contract as ``MacRecorder``/``DemoRecorder``; the source is a file."""

    def __init__(self, directory: Path, audio_files: list[Path], *, is_demo: bool = False):
        if not audio_files:
            raise ValueError("Informe ao menos um arquivo WAV")
        self.directory = directory
        self.audio_files = [Path(p) for p in audio_files]
        self.is_demo = is_demo
        self.path = None
        self.used = 0
        self.history: list[dict] = []

    def _next_audio(self) -> bytes:
        index = min(self.used, len(self.audio_files) - 1)
        self.used += 1
        source = self.audio_files[index]
        pcm = wav_to_pcm16k(source)
        self.history.append({"arquivo": source.name, "segundos": round(len(pcm) / (RATE * 2), 2)})
        return pcm

    def start(self, sid):
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / f"capture_{sid}.raw"
        self.path.write_bytes(self._next_audio())

    def recover(self, sid, *, confirmed_bytes=0):
        self.start(sid)

    def pause(self):
        pass

    def resume(self):
        pass

    def finish(self):
        return self.path

    def abort(self):
        pass

    def check(self):
        pass

    def probe(self):
        missing = [p.name for p in self.audio_files if not p.is_file()]
        status = "error" if missing else "ready"
        message = (
            f"Arquivo de audio ausente: {', '.join(missing)}"
            if missing
            else f"Microfone substituido por {len(self.audio_files)} arquivo(s) WAV"
        )
        return [
            {"component": "microphone", "status": status, "message": message},
            {"component": "permission", "status": "skipped", "message": "Captura por arquivo"},
            {"component": "device", "status": "skipped", "message": "Captura por arquivo"},
        ]

    def calibrate(self):
        return {
            "status": "skipped",
            "device_id": "file",
            "quality": "unknown",
            "message": "Captura por arquivo nao calibra microfone",
            "duration_seconds": 0,
            "valid": False,
        }

    def voice(self):
        return None

    def recovery_manifest(self, sid):
        path = self.directory / f"capture_{sid}.raw"
        return {"confirmed_bytes": 0, "chunks": [], "path": str(path)}

    def confirmed_chunks(self):
        return []

    def final_remainder(self):
        if self.path is None:
            return None
        return {
            "sequence": 0,
            "offset": 0,
            "byte_size": self.path.stat().st_size,
            "path": str(self.path),
        }

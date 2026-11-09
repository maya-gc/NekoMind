"""Generate the student's spoken answer with the operating system's own voice.

No loudspeaker and no microphone are involved: the speech goes straight to a
WAV file (16 kHz, mono, 16-bit) that ``FileRecorder`` feeds to the bridge.

* Windows: ``System.Speech`` (SAPI) through Windows PowerShell, preferring a
  pt-BR voice such as "Microsoft Maria" when installed.
* macOS: ``say`` (voice "Luciana" when available).
* Others / fallback: ``espeak-ng`` if present, otherwise a synthetic tone that
  is clearly reported as such (it does not represent speech).
"""

from __future__ import annotations

import math
import os
import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path

RATE = 16000


def _windows(text: str, out: Path) -> str:
    script = (
        "Add-Type -AssemblyName System.Speech;"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        "$v = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -eq 'pt-BR' }"
        " | Select-Object -First 1;"
        "if ($v) { $s.SelectVoice($v.VoiceInfo.Name) };"
        "$f = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo("
        "16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,"
        " [System.Speech.AudioFormat.AudioChannel]::Mono);"
        "$s.SetOutputToWaveFile($env:NEKO_OUT, $f);"
        "$s.Speak($env:NEKO_TEXT); $s.Dispose();"
        "if ($v) { 'voz=' + $v.VoiceInfo.Name } else { 'voz=padrao' }"
    )
    env = {**os.environ, "NEKO_OUT": str(out), "NEKO_TEXT": text}
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    if result.returncode != 0 or not out.is_file():
        raise RuntimeError(result.stderr.strip() or "SAPI nao gerou audio")
    return result.stdout.strip()


def _macos(text: str, out: Path) -> str:
    voices = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
    args = ["say", "--data-format=LEI16@16000", "--file-format=WAVE", "-o", str(out)]
    voice = "Luciana" if "Luciana" in voices else None
    if voice:
        args[1:1] = ["-v", voice]
    subprocess.run([*args, text], check=True, timeout=120)
    return f"voz={voice or 'padrao'}"


def _espeak(text: str, out: Path) -> str:
    subprocess.run(["espeak-ng", "-v", "pt-br", "-w", str(out), text], check=True, timeout=120)
    return "voz=espeak-ng"


def _tone(text: str, out: Path) -> str:
    """Non-speech fallback: short tone bursts sized like the sentence."""
    seconds = max(1.5, min(len(text) / 12, 12))
    frames = bytearray()
    for i in range(int(RATE * seconds)):
        on = (i // 2400) % 2 == 0
        value = int(8000 * math.sin(2 * math.pi * 220 * i / RATE)) if on else 0
        frames += struct.pack("<h", value)
    with wave.open(str(out), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        wav.writeframes(bytes(frames))
    return "voz=tom-sintetico (nao e fala)"


def synthesize(text: str, out: Path, *, allow_tone: bool = True) -> dict:
    """Write ``text`` as speech into ``out``; return which engine was used."""
    out.parent.mkdir(parents=True, exist_ok=True)
    attempts = []
    if sys.platform == "win32":
        attempts.append(("sapi", _windows))
    elif sys.platform == "darwin":
        attempts.append(("say", _macos))
    if shutil.which("espeak-ng"):
        attempts.append(("espeak-ng", _espeak))
    errors = []
    for name, engine in attempts:
        try:
            detail = engine(text, out)
            return {"engine": name, "detail": detail, "is_speech": True, "path": str(out)}
        except Exception as exc:  # noqa: BLE001 - try the next engine
            errors.append(f"{name}: {exc}")
    if not allow_tone:
        raise RuntimeError("Nenhuma voz do sistema disponivel: " + "; ".join(errors))
    detail = _tone(text, out)
    return {"engine": "tone", "detail": detail, "is_speech": False, "path": str(out),
            "errors": errors}

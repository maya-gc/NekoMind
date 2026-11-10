"""Portability adapters and the automated pipeline (runs on Windows and macOS)."""

import json
import os
import wave
from array import array

import pytest

from app import platform_support
from app.mac.file_capture import FileRecorder, wav_to_pcm16k
from app.mac.speaker import SilentSpeaker


def write_wav(path, seconds=0.5, rate=22050, channels=2):
    frames = array("h", [1000, -1000] * int(rate * seconds * channels / 2))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(frames.tobytes())
    return path


def test_exclusive_lock_blocks_second_holder(tmp_path):
    path = tmp_path / "bridge.lock"
    with path.open("a") as first, path.open("a") as second:
        platform_support.lock_exclusive_nonblocking(first)
        with pytest.raises(BlockingIOError):
            platform_support.lock_exclusive_nonblocking(second)


def test_private_file_helpers(tmp_path):
    path = tmp_path / "token"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    fd = platform_support.open_regular_readonly(path)
    try:
        assert platform_support.is_private_file(os.fstat(fd))
    finally:
        os.close(fd)
    assert not platform_support.is_private_file(os.stat(tmp_path))


def test_open_regular_readonly_refuses_symlink(tmp_path):
    target = tmp_path / "real"
    target.write_text("x")
    link = tmp_path / "link"
    try:
        link.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"Sistema nao permite criar link simbolico: {exc}")
    with pytest.raises((OSError, RuntimeError)):
        os.close(platform_support.open_regular_readonly(link))


def test_audio_player_command_matches_platform(tmp_path):
    command = platform_support.audio_player_command(tmp_path / "a.wav")
    if platform_support.IS_MACOS:
        assert command[0] == "/usr/bin/afplay"  # macOS path unchanged
    elif platform_support.IS_WINDOWS:
        assert command[0] == "powershell"
    else:
        assert command is None


def test_file_recorder_converts_to_bridge_format(tmp_path):
    first = write_wav(tmp_path / "a.wav", seconds=0.5)
    second = write_wav(tmp_path / "b.wav", seconds=1.0, rate=16000, channels=1)
    recorder = FileRecorder(tmp_path / "capture", [first, second])
    recorder.start(7)
    size = recorder.final_remainder()["byte_size"]
    assert abs(size - 16000 * 2 * 0.5) < 64
    recorder.start(8)
    assert recorder.finish().stat().st_size == len(wav_to_pcm16k(second)) == 32000
    recorder.start(9)  # last file repeats
    assert [h["arquivo"] for h in recorder.history] == ["a.wav", "b.wav", "b.wav"]
    assert recorder.probe()[0]["status"] == "ready"


def test_silent_speaker_records_without_playing(tmp_path):
    speaker = SilentSpeaker(tmp_path / "voz")
    speaker.speak("Como você explicaria  a chuva?")
    speaker.stop()
    lines = speaker.log_path.read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["fala"] == "Como você explicaria a chuva?"
    assert speaker.spoken == ["Como você explicaria a chuva?"]


def test_automated_pipeline_demo_and_guided(client, tmp_path, monkeypatch):
    from app.devtools import os_voice, pipeline
    from app.services import audio_processing, semantic_graph

    def fake_voice(text, out, **kwargs):
        out.parent.mkdir(parents=True, exist_ok=True)
        write_wav(out, seconds=1.0, rate=16000, channels=1)
        return {"engine": "teste", "detail": "voz=teste", "is_speech": True, "path": str(out)}

    def no_graph(*args, **kwargs):
        raise semantic_graph.SemanticGraphError("offline")

    monkeypatch.setattr(os_voice, "synthesize", fake_voice)
    monkeypatch.setattr(audio_processing, "validate_speech", lambda p, **k: {"speech_seconds": 1})
    monkeypatch.setattr(semantic_graph, "build_semantic_graph", no_graph)
    report = pipeline.run(tmp_path / "out", ["demo", "guiado", "longo", "errada", "queda_usb"],
                          "roteiro", timeout=30,
                          client=client)
    failed = [s for s in report.steps if not s["ok"]]
    assert not failed, failed
    names = {s["etapa"] for s in report.steps}
    assert {"Toque Pedir dica", "2ª resposta -> comparação"} <= names
    assert (tmp_path / "out" / "relatorio.md").is_file()
    assert "APROVADO" in (tmp_path / "out" / "relatorio.html").read_text(encoding="utf-8")
    assert {"Pergunta sobre a missão escolhida", "Toque Retomar -> gravando"} <= names
    lines = (tmp_path / "out" / "guiado" / "serial.jsonl").read_text(encoding="utf-8")
    sent = [json.loads(json.loads(line)["tx"])["command"]
            for line in lines.splitlines() if '"tx"' in line]
    assert {"diagnose", "start", "finish", "hint", "answer"} <= set(sent)


def test_ai_tutor_adapts_question_hint_and_comparison(client, tmp_path, monkeypatch):
    from app.devtools import os_voice, pipeline
    from app.services import audio_processing, semantic_graph, tutor_ai

    def fake_voice(text, out, **kwargs):
        out.parent.mkdir(parents=True, exist_ok=True)
        write_wav(out, seconds=1.0, rate=16000, channels=1)
        return {"engine": "teste", "detail": "voz=teste", "is_speech": True, "path": str(out)}

    def no_graph(*args, **kwargs):
        raise semantic_graph.SemanticGraphError("offline")

    monkeypatch.setattr(os_voice, "synthesize", fake_voice)
    monkeypatch.setattr(audio_processing, "validate_speech", lambda p, **k: {"speech_seconds": 1})
    monkeypatch.setattr(semantic_graph, "build_semantic_graph", no_graph)
    monkeypatch.setenv("NEKOMIND_TUTOR_PROVIDER", "ollama")
    seen = {}

    def first(point, transcript, model, **k):
        seen.update(k)
        return {"question": "Como a Hamiltoniana dita a evolução no tempo?",
                "hint": "Dica: lembre da equação de Schrödinger.",
                "hints": ["Dica: lembre da equação de Schrödinger.",
                          "Dica: pense em H como o motor do relógio do sistema."],
                "assessment": "parcial", "misconception": ""}

    monkeypatch.setattr(tutor_ai, "first_turn", first)
    monkeypatch.setattr(tutor_ai, "warm_up", lambda model: True)
    monkeypatch.setattr(tutor_ai, "second_turn", lambda *a, **k: {
        "comparison": "Agora você ligou H à evolução temporal; falta citar autovalores.",
        "assessment": "parcial"})
    report = pipeline.run(tmp_path / "out", ["complexo"], "roteiro", timeout=30, client=client)
    failed = [s for s in report.steps if not s["ok"]]
    assert not failed, failed
    detail = " ".join(s["detalhe"] for s in report.steps)
    assert "Schrödinger" in detail and "autovalores" in detail
    assert "motor do relógio" in detail  # segunda dica, mais forte que a primeira
    assert seen.get("level") == "enem" and "1 ponto(s) para revisar" in detail


def test_decks_cover_simple_and_complex_and_import_once(client):
    from app.devtools import decks

    levels = {d["nivel"] for d in decks.load()}
    assert levels == {"simples", "complexo"}
    assert len(decks.import_decks(client)) == len(decks.load())
    assert decks.import_decks(client) == []


def test_asr_receives_material_vocabulary(tmp_path):
    from app.adapters import asr_adapter as asr

    calls = []

    class Model:
        def transcribe(self, source, **kwargs):
            calls.append(kwargs)
            return iter(()), None

    adapter = asr.FasterWhisperAdapter()
    adapter._load = lambda: Model()
    wav = write_wav(tmp_path / "a.wav", seconds=0.2, rate=16000, channels=1)
    adapter.transcribe(wav, "Hamiltoniana Schrödinger autovalores")
    adapter.transcribe(wav)
    assert calls[0]["initial_prompt"].startswith("Hamiltoniana") and "initial_prompt" not in calls[1]


def test_ai_tutor_bounds_text_for_the_lcd():
    from app.services.tutor_ai import LIMITS, _short

    text = _short("palavra " * 80, LIMITS["comparison"])
    assert len(text.encode("utf-8")) <= LIMITS["comparison"] and text.endswith("...")

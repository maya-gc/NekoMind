"""Automated, silent end-to-end pipeline (Windows and macOS).

    python -m app.devtools.pipeline                 # demo + guided, ASR por roteiro
    python -m app.devtools.pipeline --asr whisper   # usa faster-whisper real
    python -m app.devtools.pipeline --scenario demo

What is real and what is simulated is printed in the report:

* Touch: ``VirtualTouch`` sends the firmware's JSON Lines (real codec).
* Microphone: the student's answers are spoken by the OS voice (SAPI/``say``)
  into WAV files and replayed by ``FileRecorder``. No microphone.
* Cat voice: ``SilentSpeaker`` records the phrases; nothing is played.
* Backend: real FastAPI app, SQLite, session analysis and bridge, in-process.
* ASR: ``roteiro`` returns the known script (fast, no model); ``whisper``
  transcribes the generated audio with faster-whisper.
* VAD: real WebRTC VAD when installed (validates that the OS voice is speech).

Exit code 0 only when every step passed. Report: ``<out>/relatorio.md`` and
``<out>/relatorio.json``.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import platform
import sys
import tempfile
import time
import traceback
from pathlib import Path

CONTENT_TITLE = "Ciclo da água"
CONTENT_TEXT = (
    "A água do mar evapora com o calor do Sol. "
    "O vapor sobe, esfria e forma as nuvens. "
    "As gotas das nuvens caem como chuva."
)
ANSWER_1 = "A água do mar evapora com o calor do Sol."
ANSWER_2 = "O vapor sobe, esfria e forma as nuvens. Depois as gotas caem como chuva."
DEMO_ANSWER = "Hoje eu vou explicar a fotossíntese das plantas."


class Report:
    def __init__(self):
        self.steps: list[dict] = []
        self.info: dict = {}

    def step(self, scenario: str, name: str, ok: bool, detail: str = "", started=None):
        elapsed = round((time.monotonic() - started) * 1000) if started else None
        self.steps.append(
            {"cenario": scenario, "etapa": name, "ok": bool(ok), "detalhe": detail,
             "ms": elapsed}
        )
        mark = "OK  " if ok else "FALHA"
        print(f"[{mark}] {scenario:<8} {name}: {detail}", flush=True)
        return ok

    @property
    def ok(self):
        return bool(self.steps) and all(s["ok"] for s in self.steps)


@contextlib.contextmanager
def _env(**values):
    from app.config import get_settings

    old = {k: os.environ.get(k) for k in values}
    os.environ.update({k: str(v) for k, v in values.items()})
    get_settings.cache_clear()
    try:
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


@contextlib.contextmanager
def _patched(target, name, value):
    original = getattr(target, name)
    setattr(target, name, value)
    try:
        yield
    finally:
        setattr(target, name, original)


def _check(report, scenario, name, cond, detail, started):
    if not report.step(scenario, name, cond, detail, started):
        raise AssertionError(f"{name}: {detail}")


def _ready(touch, report, scenario):
    t = time.monotonic()
    reply = touch.tap("Diagnóstico")
    reply = touch.poll(None, lambda r: r.get("state") in {"ready", "error"}, timeout=30)
    diag = reply.get("diagnostic") or {}
    _check(report, scenario, "Diagnóstico -> pronto", reply.get("state") == "ready",
           f"estado={reply.get('state')} componente={diag}", t)
    return reply


def _until_result(reply):
    return reply.get("type") in {"result", "error"} or reply.get("state") in {"completed", "error"}


def run_demo(client, workdir: Path, audio: Path, report: Report, timeout: float):
    from app.devtools.virtual_touch import VirtualTouch
    from app.mac.backend import LocalBackend
    from app.mac.bridge import MacBridge
    from app.mac.file_capture import FileRecorder
    from app.mac.speaker import SilentSpeaker

    scenario = "demo"
    speaker = SilentSpeaker(workdir / "demo" / "voz")
    recorder = FileRecorder(workdir / "demo" / "captura", [audio], is_demo=True)
    bridge = MacBridge(LocalBackend(client=client), recorder, workdir / "demo" / "journal.db",
                       speaker=speaker)
    touch = VirtualTouch(bridge)
    try:
        t = time.monotonic()
        idle = touch.send("status")
        _check(report, scenario, "Descoberta (status)", idle.get("state") == "idle",
               f"estado={idle.get('state')} demo={idle.get('is_demo')}", t)
        _ready(touch, report, scenario)
        t = time.monotonic()
        rec = touch.tap("Começar")
        sid = rec.get("session_id")
        _check(report, scenario, "Toque Começar -> gravando", rec.get("state") == "recording",
               f"sessao={sid}", t)
        t = time.monotonic()
        paused = touch.tap("Pausar", sid)
        _check(report, scenario, "Toque Pausar", paused.get("state") == "paused", "", t)
        t = time.monotonic()
        resumed = touch.tap("Continuar", sid)
        _check(report, scenario, "Toque Continuar", resumed.get("state") == "recording", "", t)
        t = time.monotonic()
        touch.tap("Finalizar", sid)
        result = touch.poll(sid, _until_result, timeout=timeout)
        _check(report, scenario, "Finalizar -> resultado",
               result.get("type") == "result" and bool(result.get("topics")),
               f"tipo={result.get('type')} topicos={result.get('topics')}", t)
        t = time.monotonic()
        reset = touch.tap("Voltar", sid)
        _check(report, scenario, "Toque Voltar -> idle", reset.get("state") == "idle", "", t)
    finally:
        bridge.close()
        _write_wire(workdir / "demo" / "serial.jsonl", touch.wire)
    return speaker


def run_guided(client, workdir: Path, answers: list[Path], transcripts: list[str],
               asr: str, report: Report, timeout: float):
    from app.devtools.virtual_touch import VirtualTouch
    from app.mac.backend import LocalBackend
    from app.mac.bridge import MacBridge
    from app.mac.file_capture import FileRecorder
    from app.mac.speaker import SilentSpeaker
    from app.services import audio_processing, transcription

    scenario = "guiado"
    patches = contextlib.ExitStack()
    if asr == "roteiro":
        from app.adapters import asr_adapter
        from app.services.transcription import TranscriptionResult

        queue = list(transcripts)

        def scripted(path, **kwargs):
            text = queue.pop(0) if len(queue) > 1 else queue[0]
            return TranscriptionResult(text, "faster_whisper", False)

        class _Ready:
            def check_available(self):
                return None

        patches.enter_context(_patched(transcription, "transcribe_audio_result", scripted))
        patches.enter_context(_patched(asr_adapter, "get_asr_adapter", lambda *a, **k: _Ready()))
    try:
        import webrtcvad  # noqa: F401

        report.info["vad"] = "webrtcvad real"
    except ImportError:
        report.info["vad"] = "simulado (webrtcvad ausente)"
        patches.enter_context(_patched(audio_processing, "validate_speech",
                                       lambda path, **k: {"speech_seconds": 1}))

    speaker = SilentSpeaker(workdir / "guiado" / "voz")
    recorder = FileRecorder(workdir / "guiado" / "captura", answers, is_demo=False)
    bridge = None
    touch = None
    with patches:
        try:
            t = time.monotonic()
            content = client.post("/api/v1/contents",
                                  json={"title": CONTENT_TITLE, "text": CONTENT_TEXT})
            ok = content.status_code == 201
            if ok:
                sel = client.put("/api/v1/experience/selection",
                                 json={"content_id": content.json()["id"]})
                ok = sel.status_code == 200
            _check(report, scenario, "Operador salva o material", ok,
                   f"HTTP {content.status_code}", t)
            bridge = MacBridge(LocalBackend(client=client), recorder,
                               workdir / "guiado" / "journal.db", speaker=speaker)
            touch = VirtualTouch(bridge)
            ready = _ready(touch, report, scenario)
            missions = ready.get("missions") or []
            _check(report, scenario, "Missões no touch", len(missions) >= 1,
                   f"{len(missions)} missão(ões): {missions[:3]}", None)
            t = time.monotonic()
            rec = touch.tap("Começar", mission_index=0)
            sid = rec.get("session_id")
            _check(report, scenario, "Toque Começar (missão 1)", rec.get("state") == "recording",
                   f"sessao={sid} demo={rec.get('is_demo')}", t)
            t = time.monotonic()
            touch.tap("Finalizar", sid)
            first = touch.poll(sid, _until_result, timeout=timeout)
            follow = first.get("followup") or {}
            _check(report, scenario, "1ª resposta -> pergunta",
                   first.get("type") == "result" and follow.get("stage") == "question",
                   f"tipo={first.get('type')} code={first.get('code')} "
                   f"pergunta={follow.get('question')!r}", t)
            t = time.monotonic()
            hint = touch.tap("Pedir dica", sid)
            h = (hint.get("followup") or {})
            _check(report, scenario, "Toque Pedir dica", h.get("stage") == "hint" and
                   bool(h.get("hint")), f"dica={h.get('hint')!r}", t)
            t = time.monotonic()
            second = touch.tap("Responder", sid)
            sid2 = second.get("session_id")
            _check(report, scenario, "Toque Responder -> 2ª gravação",
                   second.get("state") == "recording" and sid2 not in {None, sid},
                   f"sessao={sid2}", t)
            t = time.monotonic()
            touch.tap("Finalizar", sid2)
            done = touch.poll(sid2, lambda r: _until_result(r) and
                              (r.get("followup") or {}).get("stage") in {"done", None}
                              or r.get("type") == "error", timeout=timeout)
            d = done.get("followup") or {}
            _check(report, scenario, "2ª resposta -> comparação",
                   done.get("type") == "result" and d.get("stage") == "done"
                   and bool(d.get("comparison")),
                   f"comparacao={d.get('comparison')!r}", t)
            _check(report, scenario, "Gatinha falou (silencioso)", len(speaker.spoken) >= 1,
                   f"{len(speaker.spoken)} fala(s) registradas", None)
            touch.tap("Voltar", sid2)
        finally:
            if bridge is not None:
                bridge.close()
            if touch is not None:
                _write_wire(workdir / "guiado" / "serial.jsonl", touch.wire)
    report.info["capturas"] = recorder.history
    return speaker


def _write_wire(path: Path, wire):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as out:
        for item in wire:
            out.write(json.dumps(item, ensure_ascii=False) + "\n")


def _markdown(report: Report, spoken: dict) -> str:
    lines = ["# Pipeline automática NekoMind", ""]
    lines += [f"- **{k}:** {v}" for k, v in report.info.items()]
    lines += ["", "| Cenário | Etapa | Resultado | Detalhe | ms |", "|---|---|---|---|---|"]
    for s in report.steps:
        detail = str(s["detalhe"]).replace("|", "/")
        lines.append(f"| {s['cenario']} | {s['etapa']} | {'✅' if s['ok'] else '❌'} | "
                     f"{detail} | {s['ms'] if s['ms'] is not None else ''} |")
    for name, phrases in spoken.items():
        lines += ["", f"## Falas da gatinha ({name}, não reproduzidas)", ""]
        lines += [f"- {p}" for p in phrases] or ["- (nenhuma)"]
    lines += ["", f"**Resultado geral:** {'APROVADO' if report.ok else 'REPROVADO'}", ""]
    return "\n".join(lines)


def run(out: Path, scenarios: list[str], asr: str, timeout: float = 120.0,
        client=None) -> Report:
    """Run the scenarios. With ``client`` (tests) env and DB are the caller's."""
    from app.devtools.os_voice import synthesize

    out.mkdir(parents=True, exist_ok=True)
    report = Report()
    report.info.update({
        "sistema": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "toque": "virtual (protocolo JSON Lines do firmware)",
        "microfone": "substituído por WAV gerado pela voz do sistema",
        "voz da gatinha": "silenciosa (texto registrado, nada é tocado)",
        "asr": asr,
    })
    audio_dir = out / "audio"
    voices = {}
    for name, text in (("resposta1", ANSWER_1), ("resposta2", ANSWER_2), ("demo", DEMO_ANSWER)):
        voices[name] = synthesize(text, audio_dir / f"{name}.wav")
    engine = voices["resposta1"]
    report.info["voz do estudante"] = f"{engine['engine']} ({engine['detail']})"
    report.step("preparo", "Voz do sistema gerou as respostas", engine["is_speech"],
                engine["detail"])
    spoken = {}

    def go(client):
        if "demo" in scenarios:
            try:
                with _env(NEKOMIND_MODE="demo", NEKOMIND_ASR_PROVIDER="mock",
                          NEKOMIND_LLM_PROVIDER="mock"):
                    spoken["demo"] = run_demo(client, out, audio_dir / "demo.wav", report,
                                              timeout).spoken
            except Exception as exc:  # noqa: BLE001 - report and continue
                if not isinstance(exc, AssertionError):
                    report.step("demo", "Erro inesperado", False, repr(exc))
                    traceback.print_exc()
        if "guiado" in scenarios:
            try:
                with _env(NEKOMIND_MODE="real", NEKOMIND_ASR_PROVIDER="faster_whisper",
                          NEKOMIND_LLM_PROVIDER="local_keywords"):
                    spoken["guiado"] = run_guided(
                        client, out, [audio_dir / "resposta1.wav", audio_dir / "resposta2.wav"],
                        [ANSWER_1, ANSWER_2], asr, report, timeout).spoken
            except Exception as exc:  # noqa: BLE001
                if not isinstance(exc, AssertionError):
                    report.step("guiado", "Erro inesperado", False, repr(exc))
                    traceback.print_exc()

    if client is not None:
        go(client)
    else:
        from fastapi.testclient import TestClient

        from app.main import app
        from app.security import operator_token

        with TestClient(app) as local:
            local.headers["Authorization"] = f"Bearer {operator_token()}"
            go(local)

    (out / "relatorio.json").write_text(
        json.dumps({"ok": report.ok, "info": report.info, "etapas": report.steps,
                    "falas": spoken}, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "relatorio.md").write_text(_markdown(report, spoken), encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Pipeline automática e silenciosa do NekoMind")
    parser.add_argument("--scenario", choices=("todos", "demo", "guiado"), default="todos")
    parser.add_argument("--asr", choices=("roteiro", "whisper"), default="roteiro")
    parser.add_argument("--out", type=Path, default=None,
                        help="Pasta do relatório (padrão: backend/storage/pipeline/<data>)")
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args(argv)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    base = Path(__file__).resolve().parents[2] / "storage" / "pipeline"
    out = (args.out or base / stamp).resolve()
    work = Path(tempfile.mkdtemp(prefix="nekomind-pipeline-"))
    # Isolated database/storage: never touches the operator's real data.
    os.environ.update({
        "NEKOMIND_DATABASE_URL": f"sqlite:///{(work / 'pipeline.db').as_posix()}",
        "NEKOMIND_STORAGE_DIR": str(work / "audio"),
        "NEKOMIND_MAC_DATA_DIR": str(work / "mac"),
        "NEKOMIND_TTS_PROVIDER": "silent",
        "NEKOMIND_ASR_MODEL_SIZE": os.environ.get("NEKOMIND_ASR_MODEL_SIZE", "small"),
    })
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    scenarios = ["demo", "guiado"] if args.scenario == "todos" else [args.scenario]
    report = run(out, scenarios, args.asr, args.timeout)
    print(f"\nRelatório: {out / 'relatorio.md'}")
    print("RESULTADO:", "APROVADO" if report.ok else "REPROVADO")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())

"""Automated, silent end-to-end pipeline (Windows and macOS).

    python -m app.devtools.pipeline                         # todos os cenários, ASR por roteiro
    python -m app.devtools.pipeline --asr whisper           # faster-whisper real
    python -m app.devtools.pipeline --cenario guiado --cenario silencio
    python -m app.devtools.pipeline --repeticoes 10         # taxa de sucesso
    python -m app.devtools.pipeline --capturas              # fotos de /public e /touch

What is real and what is simulated is printed in the report:

* Touch: ``VirtualTouch`` sends the firmware's JSON Lines (real codec).
* Microphone: answers are spoken by the OS voice (SAPI/``say``) into WAV files
  replayed by ``FileRecorder``. Silence and noise are generated.
* Cat voice: ``SilentSpeaker`` records the phrases; nothing is played.
* Backend: real FastAPI app, SQLite, session analysis and bridge, in-process.
* ASR: ``roteiro`` returns the known script; ``whisper`` uses faster-whisper.
* VAD/audio quality: real (WebRTC VAD when installed).

Exit code 0 only when every step passed. Reports: ``relatorio.md``,
``relatorio.html`` and ``relatorio.json`` in ``--out``.
"""

from __future__ import annotations

import argparse
import contextlib
import html
import json
import os
import platform
import random
import sys
import tempfile
import time
import traceback
import warnings
import wave
from array import array
from pathlib import Path

CONTENT_TITLE = "Ciclo da água"
CONTENT_TEXT = (
    "A água do mar evapora com o calor do Sol. "
    "O vapor sobe, esfria e forma as nuvens. "
    "As gotas das nuvens caem como chuva."
)
LONG_TITLE = "Fotossíntese"
LONG_POINTS = [
    "A planta absorve luz do Sol",
    "As raízes puxam água do solo",
    "As folhas captam gás carbônico",
    "A clorofila transforma luz em energia",
    "A planta libera oxigênio no ar",
]
LONG_TEXT = ". ".join(LONG_POINTS) + "."

SPEECH = {
    "resposta1": "A água do mar evapora com o calor do Sol.",
    "resposta2": "O vapor sobe, esfria e forma as nuvens. Depois as gotas caem como chuva.",
    "demo": "Hoje eu vou explicar a fotossíntese das plantas.",
    "errada": "Eu gosto de jogar futebol com meus amigos no sábado.",
    "longo": "A clorofila transforma a luz em energia para a planta crescer.",
}

ALL_SCENARIOS = ["demo", "guiado", "longo", "errada", "silencio", "ruido", "queda_usb"]

# Orçamento de tempo por etapa (ms). Com --asr whisper o dobro + 20 s.
BUDGET_MS = {
    "Diagnóstico -> pronto": 5000,
    "Finalizar -> resultado": 8000,
    "1ª resposta -> pergunta": 10000,
    "2ª resposta -> comparação": 10000,
    "Resposta -> erro claro": 8000,
    "Resposta -> resultado": 10000,
}


class Report:
    def __init__(self, budget_factor=1.0, budget_extra=0, strict_time=False):
        self.steps: list[dict] = []
        self.info: dict = {}
        self.screens: list[dict] = []
        self.round = 1
        self.budget_factor, self.budget_extra, self.strict_time = (
            budget_factor, budget_extra, strict_time)

    def step(self, scenario: str, name: str, ok: bool, detail: str = "", started=None):
        elapsed = round((time.monotonic() - started) * 1000) if started else None
        budget = BUDGET_MS.get(name)
        slow = False
        if budget is not None and elapsed is not None:
            budget = round(budget * self.budget_factor + self.budget_extra)
            slow = elapsed > budget
            if slow and self.strict_time:
                ok = False
                detail = f"{detail} [lento: {elapsed} ms > {budget} ms]"
        self.steps.append(
            {"rodada": self.round, "cenario": scenario, "etapa": name, "ok": bool(ok),
             "detalhe": detail, "ms": elapsed, "orcamento_ms": budget, "lento": slow}
        )
        mark = "OK  " if ok else "FALHA"
        lento = " (lento)" if slow else ""
        print(f"[{mark}] {scenario:<9} {name}: {detail}{lento}", flush=True)
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


def _until_result(reply):
    return reply.get("type") in {"result", "error"} or reply.get("state") in {"completed", "error"}


# --------------------------------------------------------------------------- audio


def _write_pcm(path: Path, samples: array):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(samples.tobytes())


def make_silence(path: Path, seconds=3.0):
    _write_pcm(path, array("h", [0]) * int(16000 * seconds))


def make_noisy(source: Path, path: Path, noise_rms=1200, seed=7):
    from app.mac.file_capture import wav_to_pcm16k

    clean = array("h")
    clean.frombytes(wav_to_pcm16k(source))
    rnd = random.Random(seed)
    noisy = array("h", (max(-32768, min(32767, int(s + rnd.gauss(0, noise_rms)))) for s in clean))
    _write_pcm(path, noisy)


# --------------------------------------------------------------------------- screens


class Screens:
    """Optional screenshots of /public and /touch through a real HTTP server."""

    def __init__(self, out: Path, report: Report):
        self.out, self.report = out / "telas", report
        self.server = self.thread = self.browser = self.pw = None
        self.base = None

    def start(self):
        import socket
        import threading

        import uvicorn
        from playwright.sync_api import sync_playwright

        from app.main import app

        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning",
                                lifespan="off")
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        deadline = time.monotonic() + 10
        while not self.server.started and time.monotonic() < deadline:
            time.sleep(0.1)
        self.base = f"http://127.0.0.1:{port}"
        self.pw = sync_playwright().start()
        errors = []
        for kwargs in ({"channel": "msedge"}, {"channel": "chrome"}, {}):
            try:
                self.browser = self.pw.chromium.launch(**kwargs)
                self.report.info["capturas"] = f"navegador {kwargs.get('channel', 'chromium')}"
                break
            except Exception as exc:  # noqa: BLE001 - try next browser
                errors.append(str(exc).splitlines()[0])
        if self.browser is None:
            raise RuntimeError("Nenhum navegador para capturas: " + "; ".join(errors))
        self.out.mkdir(parents=True, exist_ok=True)

    def shot(self, scenario: str, label: str):
        if self.browser is None:
            return
        for page_name, size in (("public", (1440, 900)), ("touch", (240, 320))):
            name = f"r{self.report.round}-{scenario}-{label}-{page_name}.png"
            try:
                page = self.browser.new_page(viewport={"width": size[0], "height": size[1]},
                                             device_scale_factor=2 if page_name == "touch" else 1)
                page.goto(f"{self.base}/{page_name}", wait_until="networkidle", timeout=15000)
                page.wait_for_timeout(1200)
                page.screenshot(path=str(self.out / name))
                page.close()
                self.report.screens.append({"cenario": scenario, "etapa": label,
                                            "tela": page_name, "arquivo": f"telas/{name}"})
            except Exception as exc:  # noqa: BLE001 - screenshots never fail the run
                self.report.info.setdefault("avisos", []).append(f"captura {name}: {exc}")

    def stop(self):
        with contextlib.suppress(Exception):
            if self.browser:
                self.browser.close()
            if self.pw:
                self.pw.stop()
        if self.server:
            self.server.should_exit = True
            self.thread.join(timeout=5)


class _NoScreens:
    def shot(self, *a, **k):
        return None


# --------------------------------------------------------------------------- scenarios


class Session:
    """Bridge + virtual touch + silent speaker for one scenario."""

    def __init__(self, client, workdir: Path, name: str, audio: list[Path], demo: bool):
        from app.devtools.virtual_touch import VirtualTouch
        from app.mac.backend import LocalBackend
        from app.mac.bridge import MacBridge
        from app.mac.file_capture import FileRecorder
        from app.mac.speaker import SilentSpeaker

        base = workdir / name
        self.speaker = SilentSpeaker(base / "voz")
        self.recorder = FileRecorder(base / "captura", audio, is_demo=demo)
        self.bridge = MacBridge(LocalBackend(client=client), self.recorder, base / "journal.db",
                                speaker=self.speaker)
        self.touch = VirtualTouch(self.bridge)
        self.wire_path = base / "serial.jsonl"

    def close(self):
        with contextlib.suppress(Exception):
            self.touch.tap("Voltar", self.bridge.sid)
        # Publish the final idle snapshot before closing: a slower machine could
        # otherwise leave an older "processing" snapshot as the last word.
        with contextlib.suppress(Exception):
            self.bridge.wait_for_operations()
            self.bridge.tick(force=True)
            self.bridge.wait_for_operations()
        self.touch.close()
        self.bridge.close()
        self.wire_path.parent.mkdir(parents=True, exist_ok=True)
        with self.wire_path.open("w", encoding="utf-8") as out:
            for item in self.touch.wire:
                out.write(json.dumps(item, ensure_ascii=False) + "\n")


def _ready(s: Session, report, scenario):
    t = time.monotonic()
    s.touch.tap("Diagnóstico")
    reply = s.touch.poll(None, lambda r: r.get("state") in {"ready", "error"}, timeout=30)
    diag = reply.get("diagnostic") or {}
    _check(report, scenario, "Diagnóstico -> pronto", reply.get("state") == "ready",
           f"estado={reply.get('state')} componente={diag}", t)
    return reply


def _select_content(client, report, scenario, title, text, points=None):
    t = time.monotonic()
    payload = {"title": title, "text": text}
    if points:
        payload["points"] = points
    content = client.post("/api/v1/contents", json=payload)
    ok = content.status_code == 201
    selected = None
    if ok:
        deadline = time.monotonic() + 10
        while True:  # 409 = a sessão anterior ainda está sendo encerrada
            selected = client.put("/api/v1/experience/selection",
                                  json={"content_id": content.json()["id"]}).status_code
            if selected != 409 or time.monotonic() > deadline:
                break
            time.sleep(0.3)
        ok = selected == 200
    _check(report, scenario, "Operador salva o material", ok,
           f"conteúdo HTTP {content.status_code}, seleção HTTP {selected}", t)


def _start(s, report, scenario, mission=0):
    t = time.monotonic()
    rec = s.touch.tap("Começar", mission_index=mission)
    _check(report, scenario, f"Toque Começar (missão {mission + 1})",
           rec.get("state") == "recording", f"sessao={rec.get('session_id')}", t)
    return rec["session_id"]


def scenario_demo(ctx):
    report, scenario = ctx["report"], "demo"
    # Modo livre: sem material selecionado (rodadas seguintes herdam o guiado).
    ctx["client"].put("/api/v1/experience/selection", json={"content_id": None})
    s = Session(ctx["client"], ctx["out"], scenario, [ctx["audio"] / "demo.wav"], demo=True)
    try:
        t = time.monotonic()
        idle = s.touch.send("status")
        _check(report, scenario, "Descoberta (status)", idle.get("state") == "idle",
               f"estado={idle.get('state')} demo={idle.get('is_demo')}", t)
        _ready(s, report, scenario)
        ctx["screens"].shot(scenario, "pronto")
        t = time.monotonic()
        rec = s.touch.tap("Começar")
        sid = rec.get("session_id")
        _check(report, scenario, "Toque Começar -> gravando", rec.get("state") == "recording",
               f"sessao={sid}", t)
        ctx["screens"].shot(scenario, "gravando")
        t = time.monotonic()
        _check(report, scenario, "Toque Pausar",
               s.touch.tap("Pausar", sid).get("state") == "paused", "", t)
        t = time.monotonic()
        _check(report, scenario, "Toque Continuar",
               s.touch.tap("Continuar", sid).get("state") == "recording", "", t)
        t = time.monotonic()
        s.touch.tap("Finalizar", sid)
        result = s.touch.poll(sid, _until_result, timeout=ctx["timeout"])
        _check(report, scenario, "Finalizar -> resultado",
               result.get("type") == "result" and bool(result.get("topics")),
               f"tipo={result.get('type')} code={result.get('code')} "
               f"topicos={result.get('topics')}", t)
        ctx["screens"].shot(scenario, "resultado")
    finally:
        s.close()
    return s.speaker.spoken


def scenario_guided(ctx):
    report, scenario = ctx["report"], "guiado"
    _select_content(ctx["client"], report, scenario, CONTENT_TITLE, CONTENT_TEXT)
    ctx["transcripts"][:] = [SPEECH["resposta1"], SPEECH["resposta2"]]
    s = Session(ctx["client"], ctx["out"], scenario,
                [ctx["audio"] / "resposta1.wav", ctx["audio"] / "resposta2.wav"], demo=False)
    try:
        ready = _ready(s, report, scenario)
        missions = ready.get("missions") or []
        _check(report, scenario, "Missões no touch", len(missions) >= 1,
               f"{len(missions)} missão(ões): {missions[:3]}", None)
        ctx["screens"].shot(scenario, "missoes")
        sid = _start(s, report, scenario)
        t = time.monotonic()
        s.touch.tap("Finalizar", sid)
        first = s.touch.poll(sid, _until_result, timeout=ctx["timeout"])
        follow = first.get("followup") or {}
        _check(report, scenario, "1ª resposta -> pergunta",
               first.get("type") == "result" and follow.get("stage") == "question",
               f"tipo={first.get('type')} code={first.get('code')} "
               f"pergunta={follow.get('question')!r}", t)
        ctx["screens"].shot(scenario, "pergunta")
        t = time.monotonic()
        h = s.touch.tap("Pedir dica", sid).get("followup") or {}
        _check(report, scenario, "Toque Pedir dica", h.get("stage") == "hint" and
               bool(h.get("hint")), f"dica={h.get('hint')!r}", t)
        t = time.monotonic()
        second = s.touch.tap("Responder", sid)
        sid2 = second.get("session_id")
        _check(report, scenario, "Toque Responder -> 2ª gravação",
               second.get("state") == "recording" and sid2 not in {None, sid},
               f"sessao={sid2}", t)
        t = time.monotonic()
        s.touch.tap("Finalizar", sid2)
        done = s.touch.poll(sid2, lambda r: r.get("type") == "error" or (
            _until_result(r) and (r.get("followup") or {}).get("stage") == "done"),
            timeout=ctx["timeout"])
        d = done.get("followup") or {}
        _check(report, scenario, "2ª resposta -> comparação",
               done.get("type") == "result" and d.get("stage") == "done"
               and bool(d.get("comparison")), f"comparacao={d.get('comparison')!r}", t)
        ctx["screens"].shot(scenario, "comparacao")
        _check(report, scenario, "Gatinha falou (silencioso)", len(s.speaker.spoken) >= 1,
               f"{len(s.speaker.spoken)} fala(s) registradas", None)
    finally:
        s.close()
    report.info["capturas_guiado"] = s.recorder.history
    return s.speaker.spoken


def scenario_long(ctx):
    report, scenario = ctx["report"], "longo"
    _select_content(ctx["client"], report, scenario, LONG_TITLE, LONG_TEXT, LONG_POINTS)
    ctx["transcripts"][:] = [SPEECH["longo"]]
    s = Session(ctx["client"], ctx["out"], scenario, [ctx["audio"] / "longo.wav"], demo=False)
    try:
        ready = _ready(s, report, scenario)
        missions = ready.get("missions") or []
        _check(report, scenario, "Cinco missões no touch", len(missions) == len(LONG_POINTS),
               f"{len(missions)} missões", None)
        sid = _start(s, report, scenario, mission=3)
        t = time.monotonic()
        s.touch.tap("Finalizar", sid)
        result = s.touch.poll(sid, _until_result, timeout=ctx["timeout"])
        follow = result.get("followup") or {}
        _check(report, scenario, "Resposta -> resultado", result.get("type") == "result",
               f"tipo={result.get('type')} code={result.get('code')}", t)
        _check(report, scenario, "Pergunta sobre a missão escolhida",
               follow.get("point_index") == 3,
               f"ponto={follow.get('point_index')} pergunta={follow.get('question')!r}", None)
    finally:
        s.close()
    return s.speaker.spoken


def scenario_wrong(ctx):
    report, scenario = ctx["report"], "errada"
    _select_content(ctx["client"], report, scenario, CONTENT_TITLE, CONTENT_TEXT)
    ctx["transcripts"][:] = [SPEECH["errada"]]
    s = Session(ctx["client"], ctx["out"], scenario, [ctx["audio"] / "errada.wav"], demo=False)
    try:
        _ready(s, report, scenario)
        sid = _start(s, report, scenario)
        t = time.monotonic()
        s.touch.tap("Finalizar", sid)
        result = s.touch.poll(sid, _until_result, timeout=ctx["timeout"])
        follow = result.get("followup") or {}
        clear = result.get("type") == "result" or bool(result.get("code"))
        _check(report, scenario, "Resposta -> resultado", clear,
               f"tipo={result.get('type')} code={result.get('code')} "
               f"pergunta={follow.get('question')!r}", t)
        if result.get("type") == "result":
            _check(report, scenario, "Sem cobertura inventada", follow.get("stage") == "question",
                   f"estagio={follow.get('stage')} topicos={result.get('topics')}", None)
    finally:
        s.close()
    return s.speaker.spoken


def scenario_silence(ctx):
    report, scenario = ctx["report"], "silencio"
    if ctx["vad_patched"]:
        report.step(scenario, "Pulado", True, "VAD simulado: instale webrtcvad para este cenário")
        return []
    _select_content(ctx["client"], report, scenario, CONTENT_TITLE, CONTENT_TEXT)
    ctx["transcripts"][:] = [""]
    s = Session(ctx["client"], ctx["out"], scenario, [ctx["audio"] / "silencio.wav"], demo=False)
    try:
        _ready(s, report, scenario)
        sid = _start(s, report, scenario)
        t = time.monotonic()
        s.touch.tap("Finalizar", sid)
        result = s.touch.poll(sid, _until_result, timeout=ctx["timeout"])
        _check(report, scenario, "Resposta -> erro claro",
               result.get("type") == "error" and bool(result.get("code")),
               f"tipo={result.get('type')} code={result.get('code')} "
               f"msg={result.get('message')!r}", t)
        ctx["screens"].shot(scenario, "erro")
    finally:
        s.close()
    return s.speaker.spoken


def scenario_noise(ctx):
    report, scenario = ctx["report"], "ruido"
    _select_content(ctx["client"], report, scenario, CONTENT_TITLE, CONTENT_TEXT)
    ctx["transcripts"][:] = [SPEECH["resposta1"]]
    s = Session(ctx["client"], ctx["out"], scenario, [ctx["audio"] / "ruido.wav"], demo=False)
    try:
        _ready(s, report, scenario)
        sid = _start(s, report, scenario)
        t = time.monotonic()
        s.touch.tap("Finalizar", sid)
        result = s.touch.poll(sid, _until_result, timeout=ctx["timeout"])
        ok = result.get("type") == "result" or (
            result.get("type") == "error" and bool(result.get("code")))
        _check(report, scenario, "Resposta -> resultado", ok,
               f"tipo={result.get('type')} code={result.get('code')}", t)
    finally:
        s.close()
    return s.speaker.spoken


def scenario_usb_drop(ctx):
    report, scenario = ctx["report"], "queda_usb"
    _select_content(ctx["client"], report, scenario, CONTENT_TITLE, CONTENT_TEXT)
    ctx["transcripts"][:] = [SPEECH["resposta1"]]
    s = Session(ctx["client"], ctx["out"], scenario, [ctx["audio"] / "resposta1.wav"],
                demo=False)
    try:
        _ready(s, report, scenario)
        sid = _start(s, report, scenario)
        t = time.monotonic()
        s.bridge.mark_serial_disconnected()
        s.bridge.disconnect()  # what run_serial does when the USB cable drops
        after = s.touch.send("status", sid)
        _check(report, scenario, "Cabo USB cai -> recuperação",
               after.get("state") == "recovery", f"estado={after.get('state')} "
               f"code={after.get('code')}", t)
        t = time.monotonic()
        back = s.touch.tap("Retomar", sid)
        _check(report, scenario, "Toque Retomar -> gravando", back.get("state") == "recording",
               f"estado={back.get('state')}", t)
        t = time.monotonic()
        s.touch.tap("Finalizar", sid)
        result = s.touch.poll(sid, _until_result, timeout=ctx["timeout"])
        _check(report, scenario, "Finalizar -> resultado", result.get("type") == "result",
               f"tipo={result.get('type')} code={result.get('code')}", t)
    finally:
        s.close()
    return s.speaker.spoken


SCENARIOS = {
    "demo": (scenario_demo, "demo"),
    "guiado": (scenario_guided, "real"),
    "longo": (scenario_long, "real"),
    "errada": (scenario_wrong, "real"),
    "silencio": (scenario_silence, "real"),
    "ruido": (scenario_noise, "real"),
    "queda_usb": (scenario_usb_drop, "real"),
}


# --------------------------------------------------------------------------- reports


def _markdown(report: Report, spoken: dict) -> str:
    lines = ["# Pipeline automática NekoMind", ""]
    lines += [f"- **{k}:** {v}" for k, v in report.info.items()]
    lines += ["", "| Rodada | Cenário | Etapa | Resultado | Detalhe | ms |",
              "|---|---|---|---|---|---|"]
    for s in report.steps:
        detail = str(s["detalhe"]).replace("|", "/")
        ms = "" if s["ms"] is None else f"{s['ms']}{' ⚠️' if s['lento'] else ''}"
        lines.append(f"| {s['rodada']} | {s['cenario']} | {s['etapa']} | "
                     f"{'✅' if s['ok'] else '❌'} | {detail} | {ms} |")
    for name, phrases in spoken.items():
        lines += ["", f"## Falas da gatinha — {name} (não reproduzidas)", ""]
        lines += [f"- {p}" for p in phrases] or ["- (nenhuma)"]
    lines += ["", f"**Resultado geral:** {'APROVADO' if report.ok else 'REPROVADO'}", ""]
    return "\n".join(lines)


def _summary(report: Report) -> list[dict]:
    rows = {}
    for s in report.steps:
        key = (s["cenario"], s["etapa"])
        row = rows.setdefault(key, {"cenario": s["cenario"], "etapa": s["etapa"], "ok": 0,
                                    "total": 0, "ms": []})
        row["total"] += 1
        row["ok"] += int(s["ok"])
        if s["ms"] is not None:
            row["ms"].append(s["ms"])
    return list(rows.values())


def _html(report: Report, spoken: dict) -> str:
    e = html.escape
    summary = _summary(report)
    rounds = max((s["rodada"] for s in report.steps), default=1)
    passed = sum(1 for s in report.steps if s["ok"])
    total = len(report.steps)
    max_ms = max((max(r["ms"]) for r in summary if r["ms"]), default=1) or 1
    rows = []
    for r in summary:
        avg = round(sum(r["ms"]) / len(r["ms"])) if r["ms"] else None
        width = 0 if avg is None else max(2, round(260 * avg / max_ms))
        rate = r["ok"] / r["total"]
        cls = "ok" if rate == 1 else "bad"
        bar = (f'<svg width="270" height="14" role="img" aria-label="{avg} ms">'
               f'<rect width="{width}" height="14" rx="3" class="bar"/></svg> {avg} ms'
               if avg is not None else "")
        rows.append(f'<tr><td>{e(r["cenario"])}</td><td>{e(r["etapa"])}</td>'
                    f'<td class="{cls}">{r["ok"]}/{r["total"]}</td><td>{bar}</td></tr>')
    details = "".join(
        f'<tr><td>{s["rodada"]}</td><td>{e(s["cenario"])}</td><td>{e(s["etapa"])}</td>'
        f'<td class="{"ok" if s["ok"] else "bad"}">{"OK" if s["ok"] else "FALHA"}</td>'
        f'<td>{e(str(s["detalhe"]))}</td><td>{"" if s["ms"] is None else s["ms"]}'
        f'{" ⚠" if s["lento"] else ""}</td></tr>' for s in report.steps)
    info = "".join(f"<li><b>{e(str(k))}:</b> {e(str(v))}</li>" for k, v in report.info.items())
    voices = "".join(
        f"<h3>{e(n)}</h3><ul>{''.join(f'<li>{e(p)}</li>' for p in ph) or '<li>—</li>'}</ul>"
        for n, ph in spoken.items())
    shots = "".join(
        f'<figure><img src="{e(sc["arquivo"])}" alt="{e(sc["tela"])}" loading="lazy">'
        f'<figcaption>{e(sc["cenario"])} · {e(sc["etapa"])} · {e(sc["tela"])}</figcaption>'
        f'</figure>' for sc in report.screens)
    verdict = "APROVADO" if report.ok else "REPROVADO"
    return f"""<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Relatório NekoMind</title>
<style>
:root{{--bg:#fbf8f4;--fg:#2a2230;--muted:#6d6474;--ok:#1f7a4d;--bad:#b42335;--bar:#c86b98;--card:#fff}}
@media (prefers-color-scheme:dark){{:root{{--bg:#17131b;--fg:#efe9f3;--muted:#a79fb0;--ok:#5fd39a;--bad:#ff7d8c;--bar:#e59ac0;--card:#221c28}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}}
main{{max-width:1100px;margin:auto;padding:24px 16px}}
h1{{margin:0 0 4px}} .muted{{color:var(--muted)}}
.kpis{{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}}
.kpi{{background:var(--card);border-radius:12px;padding:12px 16px;min-width:140px}}
.kpi b{{display:block;font-size:26px}}
table{{border-collapse:collapse;width:100%;background:var(--card);border-radius:12px;overflow:hidden}}
td,th{{padding:6px 10px;border-bottom:1px solid rgba(127,127,127,.2);text-align:left;vertical-align:top}}
.ok{{color:var(--ok);font-weight:600}} .bad{{color:var(--bad);font-weight:600}}
.bar{{fill:var(--bar)}} .scroll{{overflow-x:auto}}
.shots{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}}
figure{{margin:0;background:var(--card);border-radius:12px;padding:8px}}
img{{width:100%;border-radius:8px}} figcaption{{font-size:12px;color:var(--muted)}}
</style><main>
<h1>Pipeline automática NekoMind</h1>
<p class="muted">{e(time.strftime("%d/%m/%Y %H:%M"))} · {e(report.info.get("sistema", ""))}</p>
<div class="kpis"><div class="kpi">Resultado<b class="{"ok" if report.ok else "bad"}">{verdict}</b></div>
<div class="kpi">Etapas aprovadas<b>{passed}/{total}</b></div>
<div class="kpi">Rodadas<b>{rounds}</b></div>
<div class="kpi">Capturas de tela<b>{len(report.screens)}</b></div></div>
<h2>Ambiente</h2><ul>{info}</ul>
<h2>Taxa de sucesso e tempo médio por etapa</h2><div class="scroll"><table>
<tr><th>Cenário</th><th>Etapa</th><th>Aprovadas</th><th>Tempo médio</th></tr>{"".join(rows)}</table></div>
{"<h2>Telas</h2><div class='shots'>" + shots + "</div>" if shots else ""}
<h2>Falas da gatinha (registradas, não reproduzidas)</h2>{voices}
<h2>Todas as etapas</h2><div class="scroll"><table>
<tr><th>Rodada</th><th>Cenário</th><th>Etapa</th><th>Resultado</th><th>Detalhe</th><th>ms</th></tr>{details}</table></div>
</main></html>"""


# --------------------------------------------------------------------------- runner


def _prepare_audio(out: Path, report: Report) -> Path:
    from app.devtools.os_voice import synthesize

    audio_dir = out / "audio"
    engine = None
    for name, text in SPEECH.items():
        result = synthesize(text, audio_dir / f"{name}.wav")
        engine = engine or result
    make_silence(audio_dir / "silencio.wav")
    make_noisy(audio_dir / "resposta1.wav", audio_dir / "ruido.wav")
    report.info["voz do estudante"] = f"{engine['engine']} ({engine['detail']})"
    report.step("preparo", "Voz do sistema gerou as respostas", engine["is_speech"],
                engine["detail"])
    return audio_dir


def run(out: Path, scenarios: list[str], asr: str, timeout: float = 120.0, client=None, *,
        rounds: int = 1, screenshots: bool = False, strict_time: bool = False) -> Report:
    """Run the scenarios. With ``client`` (tests) env and DB are the caller's."""
    out.mkdir(parents=True, exist_ok=True)
    whisper = asr == "whisper"
    report = Report(budget_factor=2.0 if whisper else 1.0, budget_extra=20000 if whisper else 0,
                    strict_time=strict_time)
    report.info.update({
        "sistema": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "toque": "virtual (protocolo JSON Lines do firmware)",
        "microfone": "substituído por WAV (voz do sistema, silêncio e ruído gerados)",
        "voz da gatinha": "silenciosa (texto registrado, nada é tocado)",
        "asr": asr,
        "cenarios": ", ".join(scenarios),
    })
    audio_dir = _prepare_audio(out, report)
    spoken: dict = {}

    def go(client):
        from app.services import audio_processing, transcription

        transcripts: list[str] = []
        patches = contextlib.ExitStack()
        if asr == "roteiro":
            from app.adapters import asr_adapter
            from app.services.transcription import TranscriptionResult

            original = transcription.transcribe_audio_result

            def scripted(path, **kwargs):
                from app.config import get_settings

                if get_settings().asr_provider == "mock":  # demo keeps its own mock ASR
                    return original(path, **kwargs)
                text = transcripts.pop(0) if len(transcripts) > 1 else (transcripts or [""])[0]
                return TranscriptionResult(text, "faster_whisper", False)

            class _Ready:
                def check_available(self):
                    return None

            patches.enter_context(_patched(transcription, "transcribe_audio_result", scripted))
            patches.enter_context(_patched(asr_adapter, "get_asr_adapter",
                                           lambda *a, **k: _Ready()))
        vad_patched = False
        try:
            import webrtcvad  # noqa: F401

            report.info["vad"] = "webrtcvad real"
        except ImportError:
            vad_patched = True
            report.info["vad"] = "simulado (webrtcvad ausente)"
            patches.enter_context(_patched(audio_processing, "validate_speech",
                                           lambda path, **k: {"speech_seconds": 1}))
        screens = _NoScreens()
        if screenshots:
            try:
                screens = Screens(out, report)
                screens.start()
            except Exception as exc:  # noqa: BLE001 - optional
                report.info["capturas"] = f"desligadas ({exc})"
                screens = _NoScreens()
        ctx = {"client": client, "out": out, "audio": audio_dir, "report": report,
               "timeout": timeout, "transcripts": transcripts, "screens": screens,
               "vad_patched": vad_patched}
        with patches:
            try:
                for current in range(1, rounds + 1):
                    report.round = current
                    for name in scenarios:
                        func, mode = SCENARIOS[name]
                        env = ({"NEKOMIND_MODE": "demo", "NEKOMIND_ASR_PROVIDER": "mock",
                                "NEKOMIND_LLM_PROVIDER": "mock"} if mode == "demo" else
                               {"NEKOMIND_MODE": "real",
                                "NEKOMIND_ASR_PROVIDER": "faster_whisper",
                                "NEKOMIND_LLM_PROVIDER": "local_keywords"})
                        try:
                            with _env(**env):
                                spoken[name] = func(ctx)
                        except AssertionError:
                            pass
                        except Exception as exc:  # noqa: BLE001 - report and continue
                            report.step(name, "Erro inesperado", False, repr(exc))
                            traceback.print_exc()
            finally:
                if isinstance(screens, Screens):
                    screens.stop()

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
                    "resumo": _summary(report), "telas": report.screens, "falas": spoken},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "relatorio.md").write_text(_markdown(report, spoken), encoding="utf-8")
    (out / "relatorio.html").write_text(_html(report, spoken), encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Pipeline automática e silenciosa do NekoMind")
    parser.add_argument("--cenario", action="append", choices=ALL_SCENARIOS + ["todos"],
                        help="Repita para escolher vários (padrão: todos)")
    parser.add_argument("--scenario", dest="cenario", action="append",
                        choices=ALL_SCENARIOS + ["todos"], help=argparse.SUPPRESS)
    parser.add_argument("--asr", choices=("roteiro", "whisper"), default="roteiro")
    parser.add_argument("--repeticoes", type=int, default=1)
    parser.add_argument("--capturas", action="store_true",
                        help="Fotografa /public e /touch (requer playwright)")
    parser.add_argument("--tempo-estrito", action="store_true",
                        help="Etapa acima do orçamento de tempo conta como falha")
    parser.add_argument("--out", type=Path, default=None,
                        help="Pasta do relatório (padrão: backend/storage/pipeline/<data>)")
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args(argv)
    warnings.simplefilter("ignore", DeprecationWarning)
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
    chosen = args.cenario or ["todos"]
    scenarios = ALL_SCENARIOS if "todos" in chosen else list(dict.fromkeys(chosen))
    report = run(out, scenarios, args.asr, args.timeout, rounds=max(1, args.repeticoes),
                 screenshots=args.capturas, strict_time=args.tempo_estrito)
    print(f"\nRelatório: {out / 'relatorio.html'}")
    print("RESULTADO:", "APROVADO" if report.ok else "REPROVADO")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())

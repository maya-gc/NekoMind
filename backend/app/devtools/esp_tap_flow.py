"""Hardware end-to-end with simulated taps on the REAL ESP32-S3 display.

    python -m app.devtools.esp_tap_flow                 # detecta a placa
    python -m app.devtools.esp_tap_flow --port COM3

Needs firmware with the ``!tap`` debug command (Nov/2026). The host sends
``!tap diagnose``, ``!tap start``... and the firmware runs the same hit test a
finger would, on the layout currently drawn on the LCD. Everything else is the
real chain: firmware controller, USB serial, ``run_serial``, bridge, API,
SQLite and analysis. The microphone is replaced by the OS voice (WAV), the cat
voice is silent and ASR uses the known script unless ``--asr whisper``.
Each step waits for the LCD's own ``display_ack`` receipt.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path


class AckSpy:
    """Serial wrapper: forwards I/O to ``run_serial`` and records LCD receipts."""

    def __init__(self, port):
        self.port = port
        self.lock = threading.Lock()
        self.acks: list[dict] = []
        self.logs: list[str] = []
        self.health: list[str] = []
        self._buffer = b""

    def read(self, size):
        data = self.port.read(size)
        if data:
            self._buffer += data
            while b"\n" in self._buffer:
                line, self._buffer = self._buffer.split(b"\n", 1)
                text = line.decode("utf-8", "replace").strip()
                start = text.find('{"v":1,"type":"display_ack"')
                if start >= 0:
                    with contextlib.suppress(ValueError):
                        with self.lock:
                            self.acks.append(json.loads(text[start:]))
                elif "sim_tap" in text:
                    self.logs.append(text)
                elif "saude:" in text or "avatar 3D:" in text:
                    self.health.append(text)
        return data

    def write(self, data):
        with self.lock:
            return self.port.write(data)

    def tap(self, name):
        self.write(f"!tap {name}\n".encode())

    def state(self):
        with self.lock:
            return self.acks[-1]["state"] if self.acks else None

    def wait(self, states, timeout=20.0, after=0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self.lock:
                fresh = self.acks[after:]
            for ack in fresh:
                if ack["state"] in states:
                    return ack
            time.sleep(0.1)
        return None


def health_summary(lines: list[str]) -> dict:
    """Numbers the firmware prints every ~30 s (render time, stack, cadence)."""
    import re

    worst = [int(m) for line in lines for m in re.findall(r"pior quadro (\d+) ms", line)]
    stack = [int(m) for line in lines for m in re.findall(r"pilha livre (\d+) bytes", line)]
    render = [int(m) for line in lines for m in re.findall(r"render medio (\d+) ms", line)]
    return {"pior_quadro_ms": max(worst) if worst else None,
            "pilha_livre_min": min(stack) if stack else None,
            "render_medio_ms": max(render) if render else None, "amostras": len(lines)}


def run(port_name: str, out: Path, asr: str, timeout: float, minutes: float = 0.0) -> int:
    import serial

    from app.devtools import pipeline
    from app.mac.serial_loop import run_serial

    report = pipeline.Report()
    report.info.update({"placa": port_name, "toque": "simulado DENTRO do firmware (!tap)",
                        "asr": asr, "microfone": "WAV da voz do sistema",
                        "voz da gatinha": "silenciosa"})
    audio = pipeline._prepare_audio(out, report)
    scenario = "placa"
    from fastapi.testclient import TestClient

    from app.mac.backend import LocalBackend
    from app.mac.bridge import MacBridge
    from app.mac.file_capture import FileRecorder
    from app.mac.speaker import SilentSpeaker
    from app.main import app
    from app.security import operator_token
    from app.services import transcription

    transcripts = [pipeline.SPEECH["resposta1"], pipeline.SPEECH["resposta2"]]
    patches = contextlib.ExitStack()
    if asr == "roteiro":
        from app.adapters import asr_adapter
        from app.services.transcription import TranscriptionResult

        def scripted(path, **kwargs):
            text = transcripts.pop(0) if len(transcripts) > 1 else transcripts[0]
            return TranscriptionResult(text, "faster_whisper", False)

        class _Ready:
            def check_available(self):
                return None

        patches.enter_context(pipeline._patched(transcription, "transcribe_audio_result",
                                                scripted))
        patches.enter_context(pipeline._patched(asr_adapter, "get_asr_adapter",
                                                lambda *a, **k: _Ready()))
    env = {"NEKOMIND_MODE": "real", "NEKOMIND_ASR_PROVIDER": "faster_whisper",
           "NEKOMIND_LLM_PROVIDER": "local_keywords"}
    stop = threading.Event()
    with patches, pipeline._env(**env), TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {operator_token()}"
        pipeline._select_content(client, report, scenario, pipeline.CONTENT_TITLE,
                                 pipeline.CONTENT_TEXT)
        speaker = SilentSpeaker(out / scenario / "voz")
        recorder = FileRecorder(out / scenario / "captura",
                                [audio / "resposta1.wav", audio / "resposta2.wav"])
        bridge = MacBridge(LocalBackend(client=client), recorder, out / scenario / "journal.db",
                           speaker=speaker)
        port = serial.Serial(port_name, 115200, timeout=0.1, write_timeout=2)
        spy = AckSpy(port)
        loop = threading.Thread(target=run_serial, args=(spy, bridge, stop), daemon=True)
        loop.start()

        def step(name, tap, states, check=None, wait=20.0):
            t = time.monotonic()
            mark = len(spy.acks)
            if tap:
                spy.tap(tap)
            ack = spy.wait(states, timeout=wait, after=mark)
            ok = ack is not None and (check is None or check(ack))
            detail = f"tela={ack['state'] if ack else spy.state()}"
            if ack and ack.get("mission_count"):
                detail += f" missoes={ack['mission_count']}"
            if not ok and tap and not spy.logs:
                detail += " (firmware sem !tap? grave o firmware novo)"
            return report.step(scenario, name, ok, detail, t)

        def one_round(n):
            if not loop.is_alive():
                report.step(scenario, "Laço serial do computador", False,
                            "parou (veja o erro acima); encerrando o teste")
                return False
            report.round = n
            recorder.used = 0
            transcripts[:] = [pipeline.SPEECH["resposta1"], pipeline.SPEECH["resposta2"]]
            alive = {"IDLE", "READY", "SUCCESS", "ERROR"}
            if n > 1 and spy.state() in alive:
                # A placa só redesenha quando a tela muda; o último recibo vale.
                ok = report.step(scenario, "Placa conectada (heartbeat)", True,
                                 f"tela={spy.state()} (sem mudança desde a rodada anterior)")
            else:
                ok = step("Placa conectada (heartbeat)", None, alive, wait=15)
            if ok and spy.state() != "IDLE":
                step("Voltar ao início", "reset", {"IDLE"})
            ok = ok and step("Toque Diagnóstico -> Pronto", "diagnose", {"READY"}, wait=30)
            ok = ok and step("Toque Começar -> Gravando", "start", {"RECORDING"})
            if ok:
                time.sleep(1.5)
            ok = ok and step("Toque Finalizar -> resultado", "finish", {"SUCCESS", "ERROR"},
                             check=lambda a: a["state"] == "SUCCESS", wait=timeout)
            stage = (bridge._followup_wire() or {}).get("stage")
            ok = ok and report.step(scenario, "Pergunta na tela", stage == "question",
                                    f"estagio={stage}")
            if ok:
                spy.tap("hint")
                time.sleep(2)
                stage = (bridge._followup_wire() or {}).get("stage")
                ok = report.step(scenario, "Toque Pedir dica", stage == "hint", f"estagio={stage}")
            ok = ok and step("Toque Responder -> Gravando", "answer", {"RECORDING"})
            if ok:
                time.sleep(1.5)
            ok = ok and step("Toque Finalizar -> comparação", "finish", {"SUCCESS", "ERROR"},
                             check=lambda a: a["state"] == "SUCCESS", wait=timeout)
            if ok:
                follow = bridge._followup_wire() or {}
                report.step(scenario, "Comparação na tela", follow.get("stage") == "done",
                            f"comparacao={follow.get('comparison')!r}")
            spy.tap("reset")
            time.sleep(1)
            return ok

        try:
            deadline = time.monotonic() + minutes * 60
            rounds = 0
            while True:
                rounds += 1
                if not one_round(rounds) and not loop.is_alive():
                    break
                if minutes <= 0 or time.monotonic() >= deadline:
                    break
            report.info["rodadas"] = rounds
            time.sleep(1)
            health = health_summary(spy.health)
            report.info["saude do firmware"] = health
            if health["amostras"] == 0:
                report.step(scenario, "Saúde do firmware", True,
                            "sem dados (firmware sem registro de saúde ou teste curto)")
            else:
                worst = health["pior_quadro_ms"]
                stack = health["pilha_livre_min"]
                ok_frame = worst is None or worst <= 60
                ok_stack = stack is None or stack >= 2048
                report.step(scenario, "Saúde do firmware", ok_frame and ok_stack,
                            f"pior quadro={worst} ms (limite 60), pilha livre mínima={stack} "
                            f"bytes (mínimo 2048), render médio={health['render_medio_ms']} ms")
        finally:
            stop.set()
            loop.join(timeout=5)
            port.close()
            bridge.close()
        report.info["toques registrados pelo firmware"] = len(spy.logs)
        report.info["telas desenhadas"] = len(spy.acks)
    spoken = {scenario: speaker.spoken}
    (out / "relatorio.md").write_text(pipeline._markdown(report, spoken), encoding="utf-8")
    (out / "relatorio.html").write_text(pipeline._html(report, spoken), encoding="utf-8")
    (out / "relatorio.json").write_text(json.dumps(
        {"ok": report.ok, "info": report.info, "etapas": report.steps, "acks": spy.acks,
         "firmware": spy.logs}, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report.ok else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fluxo completo na placa com toques simulados")
    parser.add_argument("--port", default=None)
    parser.add_argument("--asr", choices=("roteiro", "whisper"), default="roteiro")
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--minutos", type=float, default=0,
                        help="Teste de resistência: repete o fluxo até completar N minutos")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import warnings

    warnings.simplefilter("ignore", DeprecationWarning)
    from app.devtools.esp_probe import find_port

    port = args.port or find_port()
    if not port:
        print("RESULTADO: nenhuma placa encontrada")
        return 1
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = (args.out or Path(__file__).resolve().parents[2] / "storage" / "placa" / stamp).resolve()
    out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="nekomind-placa-"))
    os.environ.update({
        "NEKOMIND_DATABASE_URL": f"sqlite:///{(work / 'placa.db').as_posix()}",
        "NEKOMIND_STORAGE_DIR": str(work / "audio"),
        "NEKOMIND_MAC_DATA_DIR": str(work / "mac"),
    })
    code = run(port, out, args.asr, args.timeout, args.minutos)
    print(f"\nRelatório: {out / 'relatorio.html'}")
    print("RESULTADO:", "PLACA APROVADA" if code == 0 else "PLACA REPROVADA")
    return code


if __name__ == "__main__":
    sys.exit(main())

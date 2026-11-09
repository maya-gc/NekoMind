"""Pre-stage checklist: everything the live demo needs, checked in ~15 s.

    python -m app.devtools.preflight                  # modo real
    python -m app.devtools.preflight --plano-b        # demo identificado, sem modelos
    python -m app.devtools.preflight --porta COM3 --voz kokoro

Prints one line per item (OK / AVISO / FALHA) and exits 1 when something that
would break the presentation is missing, suggesting the fix or plan B.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


class Checklist:
    def __init__(self):
        self.items = []

    def add(self, name, status, detail, fix=""):
        self.items.append({"item": name, "status": status, "detalhe": detail, "como_resolver": fix})
        icon = {"ok": "OK   ", "aviso": "AVISO", "falha": "FALHA"}[status]
        print(f"[{icon}] {name}: {detail}" + (f"\n         -> {fix}" if fix else ""), flush=True)

    @property
    def blocking(self):
        return [i for i in self.items if i["status"] == "falha"]


def check_python(c):
    ok = sys.version_info >= (3, 11)
    c.add("Python", "ok" if ok else "falha", sys.version.split()[0],
          "" if ok else "Use Python 3.11 ou mais novo")
    missing = []
    for module in ("fastapi", "uvicorn", "sqlalchemy", "serial", "sounddevice"):
        try:
            __import__(module)
        except Exception:  # noqa: BLE001
            missing.append(module)
    c.add("Dependências", "falha" if missing else "ok",
          f"faltando: {', '.join(missing)}" if missing else "instaladas",
          "Rode scripts/test_auto (cria o ambiente)" if missing else "")


def check_port_8000(c):
    with socket.socket() as sock:
        busy = sock.connect_ex(("127.0.0.1", 8000)) == 0
    c.add("Porta 8000 livre", "aviso" if busy else "ok",
          "ocupada (backend já está rodando?)" if busy else "livre",
          "Feche o backend anterior ou use a instância já aberta" if busy else "")


def check_board(c, port):
    from app.devtools import esp_probe

    try:
        port = port or esp_probe.find_port()
    except Exception as exc:  # noqa: BLE001
        c.add("Placa ESP", "falha", f"pyserial indisponível: {exc}")
        return None
    if not port:
        c.add("Placa ESP", "falha", "nenhuma placa Espressif na USB",
              "Use um cabo USB de dados e outra porta; sem a placa não há touch")
        return None
    try:
        stats = esp_probe.probe(port, 6)
    except Exception as exc:  # noqa: BLE001
        c.add("Placa ESP", "falha", f"{port} não abriu: {exc}",
              "Feche monitor serial/Arduino/idf.py monitor e tente de novo")
        return port
    if stats["ok"]:
        c.add("Placa ESP", "ok", f"{port}: {stats['commands']} heartbeats, "
              f"{stats['acks']} telas desenhadas sem erro")
    else:
        c.add("Placa ESP", "falha", f"{port}: {json.dumps(stats)}",
              "Aperte RESET na placa e aguarde a tela inicial")
    return port


def check_microphone(c, plan_b):
    try:
        import sounddevice as sd

        device = sd.query_devices(kind="input")
        c.add("Microfone", "ok", f"{device['name']} ({int(device['default_samplerate'])} Hz)")
    except Exception as exc:  # noqa: BLE001
        c.add("Microfone", "aviso" if plan_b else "falha", f"não encontrado: {exc}",
              "Conecte/permita o microfone (macOS: Ajustes > Privacidade > Microfone) "
              "ou use --plano-b")


def check_asr(c, plan_b, model):
    if plan_b:
        c.add("Transcrição", "ok", "plano B: demonstrativa (identificada como DEMO)")
        return
    try:
        from faster_whisper import WhisperModel

        WhisperModel(model, device="cpu", compute_type="int8", local_files_only=True)
        c.add("Transcrição", "ok", f"faster-whisper '{model}' em cache local")
    except Exception as exc:  # noqa: BLE001
        c.add("Transcrição", "falha", f"modelo '{model}' indisponível: {str(exc)[:120]}",
              "Rode scripts/baixar_modelo_asr (uma vez, com internet) ou use --plano-b")
    try:
        import webrtcvad  # noqa: F401

        c.add("Detector de fala (VAD)", "ok", "webrtcvad instalado")
    except ImportError:
        c.add("Detector de fala (VAD)", "falha", "webrtcvad ausente",
              "pip install -r backend/requirements-real.txt")


def check_voice(c, voice):
    if voice in {"off", "silent"}:
        c.add("Voz da gatinha", "aviso", f"'{voice}': a gatinha não vai falar em voz alta")
        return
    try:
        from app.mac.speaker import KokoroSpeaker

        speaker = KokoroSpeaker(ROOT / "backend" / "storage" / "mac" / "speech",
                                play=voice == "kokoro")
        speaker.preload()
        speaker.close()
        c.add("Voz da gatinha", "ok", "Kokoro pf_dora carregada (offline)")
    except Exception as exc:  # noqa: BLE001
        setup = ("scripts\\setup_voice_windows.ps1" if os.name == "nt"
                 else "scripts/setup_voice_mac.sh")
        c.add("Voz da gatinha", "aviso", f"Kokoro indisponível: {str(exc)[:120]}",
              f"Rode {setup}; sem isso a apresentação segue sem voz")


def check_ollama(c):
    try:
        import httpx

        httpx.get("http://127.0.0.1:11434/api/tags", timeout=1.5)
        c.add("IA de briefing (Ollama)", "ok", "respondendo")
    except Exception:  # noqa: BLE001
        c.add("IA de briefing (Ollama)", "aviso", "desligada (opcional)",
              "Só é usada para sugerir pontos do material; o fluxo funciona sem ela")


def check_disk(c):
    free = shutil.disk_usage(ROOT).free / 1e9
    c.add("Espaço em disco", "ok" if free > 2 else "aviso", f"{free:.1f} GB livres")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Checklist antes de apresentar o NekoMind")
    parser.add_argument("--porta", default=None)
    parser.add_argument("--voz", default="kokoro",
                        choices=("kokoro", "kokoro-file", "silent", "off"))
    parser.add_argument("--plano-b", action="store_true")
    parser.add_argument("--modelo", default=os.environ.get("NEKOMIND_ASR_MODEL_SIZE", "small"))
    parser.add_argument("--sem-placa", action="store_true")
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("== Checklist NekoMind", "(PLANO B: demo identificado)" if args.plano_b else "(modo real)")
    c = Checklist()
    check_python(c)
    check_port_8000(c)
    port = None if args.sem_placa else check_board(c, args.porta)
    check_microphone(c, args.plano_b)
    check_asr(c, args.plano_b, args.modelo)
    check_voice(c, args.voz)
    check_ollama(c)
    check_disk(c)
    if args.json:
        args.json.write_text(json.dumps({"porta": port, "itens": c.items}, ensure_ascii=False,
                                        indent=2), encoding="utf-8")
    if c.blocking:
        print(f"\nNÃO PRONTO: {len(c.blocking)} item(ns) bloqueando.",
              "" if args.plano_b else "Para seguir mesmo assim: --plano-b")
        return 1
    print(f"\nPRONTO PARA APRESENTAR{f' (placa em {port})' if port else ''}.")
    if port:
        print(f"PORTA={port}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Run with python -m app.mac --port /dev/cu... on macOS."""

import argparse
import fcntl
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from threading import Event

from app.config import get_settings
from app.mac.backend import LocalBackend
from app.mac.bridge import MacBridge
from app.mac.capture import MacRecorder
from app.mac.serial_loop import run_serial

logger = logging.getLogger(__name__)


class DemoRecorder:
    is_demo = True

    def __init__(self, directory: Path):
        self.directory = directory
        self.path = None

    def start(self, sid):
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / f"capture_{sid}.raw"
        self.path.write_bytes(b"\x01\x00" * 16000)

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
        return [
            {
                "component": "microphone",
                "status": "skipped",
                "message": "Demo sintetico sem microfone",
            },
            {
                "component": "permission",
                "status": "skipped",
                "message": "Demo sintetico sem permissao de microfone",
            },
            {
                "component": "device",
                "status": "skipped",
                "message": "Demo sintetico sem dispositivo fisico",
            },
        ]

    def calibrate(self):
        return {
            "status": "skipped",
            "device_id": "demo",
            "quality": "unknown",
            "message": "Demo sintetico nao calibra microfone",
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


def main():
    settings = get_settings()
    parser = argparse.ArgumentParser(description="NekoMind: captura Mac controlada pelo touch")
    default_mac_dir = getattr(settings, "mac_directory", settings.storage_dir.parent / "mac")
    parser.add_argument("--port", default=settings.serial_port)
    parser.add_argument("--backend", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--device", default=None, help="Nome do dispositivo PortAudio; padrao do Mac se omitido"
    )
    parser.add_argument("--data-dir", type=Path, default=default_mac_dir)
    parser.add_argument(
        "--simulate", action="store_true", help="Usa DemoRecorder sintetico, sem microfone real"
    )
    args = parser.parse_args()
    if args.simulate and getattr(settings, "mode", "demo") != "demo":
        parser.error("--simulate exige configuracao de demo")
    if sys.platform != "darwin" and not args.simulate:
        parser.error("Este componente de captura do MVP requer macOS")
    if not args.port and not args.simulate:
        parser.error("Selecione a porta USB com --port ou NEKOMIND_SERIAL_PORT")
    os.umask(0o077)
    args.data_dir.mkdir(parents=True, exist_ok=True)
    stop = Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    # HTTP paths can include a user-defined subject. Keep transport chatter out
    # of operational logs; the bridge emits only short, content-free diagnostics.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    with (args.data_dir / "bridge.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("Ja existe um bridge para este diretorio")
        backend = LocalBackend(args.backend)
        recorder = (
            DemoRecorder(args.data_dir / "capture")
            if args.simulate
            else MacRecorder(args.data_dir / "capture", device=args.device)
        )
        bridge = MacBridge(backend, recorder, args.data_dir / "journal.db")
        awake = None
        if sys.platform == "darwin" and not args.simulate:
            # Explicitly keep this Mac awake while the bridge is running.
            awake = subprocess.Popen(["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())])
        try:
            if args.simulate and not args.port:
                logger.info("Bridge demo operacional iniciado; comandos chegam pelo backend.")
                while not stop.is_set():
                    bridge.tick()
                    for _ in bridge.drain_events():
                        pass
                    time.sleep(1)
            while not stop.is_set():
                try:
                    import serial

                    with serial.Serial(
                        args.port,
                        115200,
                        timeout=0.1,
                        write_timeout=2,
                        exclusive=True,
                    ) as port:
                        logger.info("Bridge conectado; aguardando comando touch.")
                        run_serial(port, bridge, stop)
                except (serial.SerialException, OSError):
                    bridge.disconnect()
                    logger.warning("Serial indisponivel; captura encerrada. Tentando reconectar.")
                    stop.wait(1)
        finally:
            bridge.close()
            backend.close()
            if awake is not None:
                awake.terminate()
                awake.wait(timeout=5)


if __name__ == "__main__":
    main()

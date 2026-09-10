"""Run with python -m app.mac --port /dev/cu... on macOS."""

import argparse
import fcntl
import logging
import os
import signal
import subprocess
import sys
from pathlib import Path
from threading import Event

from app.config import get_settings
from app.mac.backend import LocalBackend
from app.mac.bridge import MacBridge
from app.mac.capture import MacRecorder
from app.mac.serial_loop import run_serial

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="NekoMind: captura Mac controlada pelo touch")
    parser.add_argument("--port", default=get_settings().serial_port)
    parser.add_argument("--backend", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--device", default=None, help="Nome do dispositivo PortAudio; padrao do Mac se omitido"
    )
    parser.add_argument("--data-dir", type=Path, default=get_settings().storage_dir.parent / "mac")
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("Este componente de captura do MVP requer macOS")
    if not args.port:
        parser.error("Selecione a porta USB com --port ou NEKOMIND_SERIAL_PORT")
    os.umask(0o077)
    args.data_dir.mkdir(parents=True, exist_ok=True)
    stop = Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    import serial

    with (args.data_dir / "bridge.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("Ja existe um bridge para este diretorio")
        backend = LocalBackend(args.backend)
        recorder = MacRecorder(args.data_dir / "capture", device=args.device)
        bridge = MacBridge(backend, recorder, args.data_dir / "journal.db")
        # Explicitly keep this Mac awake while the bridge is running.
        awake = subprocess.Popen(["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())])
        try:
            while not stop.is_set():
                try:
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
            awake.terminate()
            awake.wait(timeout=5)


if __name__ == "__main__":
    main()

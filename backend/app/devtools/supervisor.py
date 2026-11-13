"""Presentation supervisor: keeps backend, bridge and Ollama alive all day.

    python -m app.devtools.supervisor --porta COM3 --voz kokoro --abrir
    python -m app.devtools.supervisor --porta /dev/cu.usbmodem1101 --plano-b

* Starts Ollama (when the tutor is on), the FastAPI backend and the USB bridge.
* Restarts any of them that exits or stops answering, with backoff.
* Writes logs to ``backend/storage/logs`` (rotated at 5 MB, 5 files kept).
* Backs up the SQLite database at start and at exit (keeps the last 10).
Ctrl+C stops everything cleanly.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
import webbrowser
from logging.handlers import RotatingFileHandler
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
STORAGE = BACKEND_DIR / "storage"
LOGS = STORAGE / "logs"
BACKUPS = STORAGE / "backups"
MAX_LOG = 5 * 1024 * 1024

log = logging.getLogger("nekomind.supervisor")


def setup_logging() -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(LOGS / "supervisor.log", maxBytes=MAX_LOG, backupCount=5,
                                  encoding="utf-8")
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(fmt)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    log.addHandler(handler)
    log.addHandler(console)
    log.setLevel(logging.INFO)


def rotate(path: Path, keep: int = 5) -> None:
    if not path.exists() or path.stat().st_size < MAX_LOG:
        return
    for i in range(keep - 1, 0, -1):
        older = path.with_suffix(f"{path.suffix}.{i}")
        if older.exists():
            older.replace(path.with_suffix(f"{path.suffix}.{i + 1}"))
    path.replace(path.with_suffix(f"{path.suffix}.1"))


def database_path() -> Path | None:
    from app.config import get_settings

    url = get_settings().database_url
    if not url.startswith("sqlite:///"):
        return None
    return Path(url.removeprefix("sqlite:///"))


def backup_database(reason: str, keep: int = 10) -> Path | None:
    """Consistent copy through SQLite's backup API (safe with WAL)."""
    source = database_path()
    if source is None or not source.exists():
        return None
    BACKUPS.mkdir(parents=True, exist_ok=True)
    target = BACKUPS / f"nekomind-{time.strftime('%Y%m%d-%H%M%S')}-{reason}.db"
    with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    for old in sorted(BACKUPS.glob("nekomind-*.db"))[:-keep]:
        old.unlink(missing_ok=True)
    log.info("Backup do banco (%s): %s", reason, target.name)
    return target


class Child:
    """A supervised process with restart backoff and its own log file."""

    def __init__(self, name: str, args: list[str], env: dict, health=None):
        self.name, self.args, self.env, self.health = name, args, env, health
        self.proc: subprocess.Popen | None = None
        self.restarts: list[float] = []
        self.failed_checks = 0

    def start(self) -> None:
        path = LOGS / f"{self.name}.log"
        rotate(path)
        handle = path.open("a", encoding="utf-8")
        handle.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} iniciando {self.name}\n")
        handle.flush()
        self.proc = subprocess.Popen(self.args, cwd=BACKEND_DIR, env=self.env, stdout=handle,
                                     stderr=subprocess.STDOUT)
        log.info("%s iniciado (pid %s)", self.name, self.proc.pid)

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def check(self) -> None:
        if not self.alive():
            code = self.proc.returncode if self.proc else None
            log.warning("%s parou (código %s); reiniciando", self.name, code)
            self.restart()
            return
        if self.health is None:
            return
        if self.health():
            self.failed_checks = 0
            return
        self.failed_checks += 1
        if self.failed_checks >= 3:
            log.warning("%s não responde há 3 verificações; reiniciando", self.name)
            self.failed_checks = 0
            self.restart()

    def restart(self) -> None:
        now = time.monotonic()
        self.restarts = [t for t in self.restarts if now - t < 300] + [now]
        if len(self.restarts) > 10:
            log.error("%s reiniciou mais de 10 vezes em 5 min; aguardando 60 s", self.name)
            time.sleep(60)
            self.restarts = []
        self.stop()
        time.sleep(min(2 * len(self.restarts), 10))
        self.start()

    def stop(self) -> None:
        if self.alive():
            self.proc.terminate()
            try:
                self.proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def backend_ok() -> bool:
    import httpx

    try:
        return httpx.get("http://127.0.0.1:8000/health", timeout=3, trust_env=False).status_code == 200
    except Exception:  # noqa: BLE001
        return False


def ollama_ok() -> bool:
    import httpx

    try:
        httpx.get("http://127.0.0.1:11434/api/tags", timeout=2, trust_env=False)
        return True
    except Exception:  # noqa: BLE001
        return False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Supervisor da apresentação do NekoMind")
    parser.add_argument("--porta", required=True)
    parser.add_argument("--voz", default="kokoro", choices=("kokoro", "kokoro-file", "silent", "off"))
    parser.add_argument("--plano-b", action="store_true")
    parser.add_argument("--modelo-tutor", default=os.environ.get("NEKOMIND_TUTOR_MODEL", "qwen2.5:7b"))
    parser.add_argument("--abrir", action="store_true", help="Abre /presenter e /public")
    args = parser.parse_args(argv)
    setup_logging()
    env = dict(os.environ)
    if args.plano_b:
        env.update(NEKOMIND_MODE="demo", NEKOMIND_ASR_PROVIDER="mock", NEKOMIND_LLM_PROVIDER="mock")
    else:
        env.update(NEKOMIND_MODE="real", NEKOMIND_ASR_PROVIDER="faster_whisper",
                   NEKOMIND_LLM_PROVIDER="local_keywords", NEKOMIND_TUTOR_MODEL=args.modelo_tutor)
    os.environ.update(env)
    backup_database("inicio")
    children: list[Child] = []
    if not args.plano_b and shutil.which("ollama") and env.get("NEKOMIND_TUTOR_PROVIDER") != "regras":
        if ollama_ok():
            log.info("Ollama já está rodando")
        else:
            children.append(Child("ollama", ["ollama", "serve"], env, ollama_ok))
    backend = Child("backend", [sys.executable, "-m", "uvicorn", "app.main:app", "--host",
                                "127.0.0.1", "--port", "8000"], env, backend_ok)
    bridge_args = [sys.executable, "-m", "app.mac", "--port", args.porta, "--voice", args.voz]
    if args.plano_b:
        bridge_args.append("--simulate")
    bridge = Child("bridge", bridge_args, env)
    children += [backend, bridge]
    stopping = False

    def _stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    for child in children[:-1]:
        child.start()
    for _ in range(60):
        if backend_ok():
            break
        time.sleep(0.5)
    bridge.start()
    if args.abrir:
        webbrowser.open("http://127.0.0.1:8000/presenter")
        webbrowser.open("http://127.0.0.1:8000/public")
    log.info("Tudo no ar. Logs em %s. Ctrl+C encerra.", LOGS)
    try:
        while not stopping:
            time.sleep(10)
            for child in children:
                if not stopping:
                    child.check()
    finally:
        log.info("Encerrando...")
        for child in reversed(children):
            child.stop()
        backup_database("fim")
    return 0


if __name__ == "__main__":
    sys.exit(main())

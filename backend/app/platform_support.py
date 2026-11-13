"""Small OS adapters so the same backend/bridge runs on macOS and Windows.

The macOS (POSIX) branch of every helper keeps the exact behaviour the MVP was
validated with: ``O_NOFOLLOW``, 0600 permission check, ``fcntl.flock`` and
``caffeinate``. Windows gets the closest native equivalent instead of a
weaker no-op wherever one exists.
"""

from __future__ import annotations

import logging
import os
import stat
import subprocess
import sys
from pathlib import Path

from app.errors import log_swallowed

logger = logging.getLogger(__name__)

IS_WINDOWS = os.name == "nt"
IS_MACOS = sys.platform == "darwin"


def open_regular_readonly(path: Path) -> int:
    """Open ``path`` for reading without following a symlink at the last hop."""
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow and Path(path).is_symlink():
        # Windows has no O_NOFOLLOW; refuse links/junctions explicitly.
        raise RuntimeError("Arquivo de acesso local nao pode ser um link.")
    return os.open(path, os.O_RDONLY | nofollow | getattr(os, "O_BINARY", 0))


def is_private_file(info: os.stat_result) -> bool:
    """True when the file is regular and readable only by its owner.

    POSIX checks the mode bits (0600). On Windows, mode bits do not describe
    ACLs (Python always reports 0o666/0o444), so privacy relies on the file
    living inside the user's profile, which NTFS restricts to the owner.
    """
    if not stat.S_ISREG(info.st_mode):
        return False
    if IS_WINDOWS:
        return True
    return not info.st_mode & 0o077


def lock_exclusive_nonblocking(handle) -> None:
    """Take an exclusive, non-blocking lock; raise ``BlockingIOError`` if held."""
    if IS_WINDOWS:
        import msvcrt

        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:  # pragma: no cover - exercised on Windows only
            raise BlockingIOError(str(exc)) from exc
        return
    import fcntl

    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)


class _WindowsAwake:
    """Ask Windows to keep the system awake while the bridge runs."""

    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001

    def __init__(self):
        import ctypes

        self._kernel = ctypes.windll.kernel32
        self._kernel.SetThreadExecutionState(self.ES_CONTINUOUS | self.ES_SYSTEM_REQUIRED)

    def terminate(self):
        self._kernel.SetThreadExecutionState(self.ES_CONTINUOUS)

    def wait(self, timeout=None):
        return 0


def keep_awake():
    """Return a handle with ``terminate()``/``wait()`` or ``None``."""
    if IS_MACOS:
        return subprocess.Popen(["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())])
    if IS_WINDOWS:
        try:
            return _WindowsAwake()
        except Exception as exc:  # noqa: BLE001 - optional comfort, never blocks capture
            log_swallowed(logger, "platform_support.keep_awake", exc)
            return None
    return None


def audio_player_command(path: Path) -> list[str] | None:
    """Command that plays a WAV file and can be terminated, or ``None``."""
    if IS_MACOS:
        return ["/usr/bin/afplay", str(path)]
    if IS_WINDOWS:
        quoted = str(path).replace("'", "''")
        return [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            f"(New-Object Media.SoundPlayer '{quoted}').PlaySync()",
        ]
    return None


def audio_player_available() -> bool:
    if IS_MACOS:
        return Path("/usr/bin/afplay").is_file()
    if IS_WINDOWS:
        return True  # Media.SoundPlayer ships with Windows PowerShell.
    return False

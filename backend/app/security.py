"""Private local operator capability. Never put this value in URLs or logs."""

import hmac
import os
import secrets
import stat
from pathlib import Path
from threading import Lock

from fastapi import Header, HTTPException

from app.config import get_settings

_lock = Lock()


def operator_token_path() -> Path:
    return get_settings().storage_dir.parent / "operator-token"


def operator_token() -> str:
    path = operator_token_path()
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "w") as out:
                out.write(secrets.token_urlsafe(32))
                out.flush()
                os.fsync(out.fileno())
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd) as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
                raise RuntimeError("Arquivo de acesso local deve ter permissao 0600.")
            value = stream.read(128).strip()
        if len(value) < 32:
            raise RuntimeError("Arquivo de acesso local invalido.")
        return value


def require_operator(authorization: str | None = Header(default=None)) -> None:
    value = (authorization or "").removeprefix("Bearer ")
    if (
        not authorization
        or not authorization.startswith("Bearer ")
        or not hmac.compare_digest(value.encode("utf-8"), operator_token().encode("utf-8"))
    ):
        raise HTTPException(status_code=401, detail="Acesso reservado ao operador local.")

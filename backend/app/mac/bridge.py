"""Single-capture bridge with durable request receipts and async analysis."""

import json
import logging
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from queue import Empty, SimpleQueue
from threading import RLock

from app.mac.protocol import Command, validate_result

logger = logging.getLogger(__name__)

MESSAGES = {
    "capture_failed": "Confira permissao e dispositivo do microfone; tente novamente.",
    "disconnected": "Conexao perdida. Captura encerrada; reconecte e tente novamente.",
    "interrupted": "Componente reiniciado. Confira a sessao e tente novamente.",
    "backend_unavailable": "Backend indisponivel. Verifique o Mac e consulte o estado.",
    "invalid_result": "Resultado invalido; nenhuma conclusao foi confirmada.",
    "request_conflict": "Identificador ja usado para outro comando.",
    "invalid_state": "Comando indisponivel neste estado; consulte o estado.",
    "invalid_command": "Comando invalido.",
}


class MacBridge:
    def __init__(self, backend, recorder, journal_path: Path):
        self.backend, self.recorder = backend, recorder
        self.lock = RLock()
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(journal_path, check_same_thread=False)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, payload TEXT NOT NULL, response TEXT)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS active (id INTEGER PRIMARY KEY CHECK(id=1), session_id INTEGER, state TEXT, demo INTEGER, code TEXT)"
        )
        row = self.db.execute("SELECT session_id,state,demo,code FROM active WHERE id=1").fetchone()
        self.sid, self.state, self.demo, self.code = row or (None, "idle", True, None)
        self.demo = bool(self.demo)
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="nekomind-analysis")
        self.future = None
        self.events = SimpleQueue()
        if self.state in {"recording", "paused"}:
            self._fail("interrupted")
        self.db.commit()

    def _save_active(self):
        self.db.execute(
            "INSERT OR REPLACE INTO active VALUES(1,?,?,?,?)",
            (self.sid, self.state, int(self.demo), self.code),
        )
        self.db.commit()

    def _fail(self, code):
        self.state, self.code = "error", code
        self._save_active()
        if self.sid is not None:
            try:
                self.backend.capture_state(self.sid, "error", code)
            except Exception:  # noqa: BLE001 - isolate capture/backend failure and persist recoverable state
                logger.warning("Falha registrada no diario local; backend indisponivel.")

    def _base(self, rid, kind="state"):
        return {
            "v": 1,
            "type": kind,
            "request_id": rid,
            "session_id": self.sid,
            "state": self.state,
            "is_demo": self.demo,
        }

    def _error(self, rid, code):
        return {
            **self._base(rid, "error"),
            "state": "error",
            "code": code,
            "message": MESSAGES.get(code, "Falha na sessao; confira a captura e tente novamente."),
        }

    def _snapshot(self, rid):
        if self.state == "error":
            return self._error(rid, self.code or "capture_failed")
        if self.state in {"processing", "completed"}:
            try:
                row = self.backend.get(self.sid)
                if row.get("status") == "error":
                    self.state, self.code = "error", row.get("error_code") or "invalid_result"
                    self._save_active()
                    return self._error(rid, self.code)
                if row.get("status") == "completed":
                    return self._result(rid, row)
                if row.get("status") not in {"processing", "recording", "paused"}:
                    return self._error(rid, "invalid_result")
                # After restart there is no uploader. Do not silently restart analysis.
                if (self.future is None or self.future.done()) and row.get(
                    "status"
                ) != "processing":
                    self._fail("interrupted")
                    return self._error(rid, "interrupted")
            except ValueError:
                self._fail("invalid_result")
                return self._error(rid, "invalid_result")
            except Exception:  # noqa: BLE001 - isolate capture/backend failure and persist recoverable state
                return self._error(rid, "backend_unavailable")
        return self._base(rid)

    def _result(self, rid, row):
        validate_result(row, self.sid)
        self.state, self.demo, self.code = "completed", row["is_demo"], None
        self._save_active()
        # UTF-8 byte limits match firmware buffers; never split a codepoint.
        shorten = lambda text, limit: text.encode()[:limit].decode("utf-8", errors="ignore")
        return {
            **self._base(rid, "result"),
            "asr_provider": row["asr_provider"],
            "topic_provider": row["topic_provider"],
            "topics": [shorten(t["name"], 120) for t in row["topics"][:8]],
            "summary": "Demonstracao concluida; dados simulados."
            if self.demo
            else "Assuntos identificados. Isso nao comprova acerto ou dominio.",
        }

    def _remember(self, rid, response):
        self.db.execute("UPDATE requests SET response=? WHERE id=?", (json.dumps(response), rid))
        self.db.commit()
        return response

    def _confirm_capture(self, state):
        row = self.backend.capture_state(self.sid, state)
        if (
            not isinstance(row, dict)
            or type(row.get("id")) is not int
            or row["id"] != self.sid
            or row.get("status") != state
        ):
            raise ValueError("Backend nao confirmou o estado da captura")

    def handle(self, message):
        try:
            cmd = Command.model_validate(message)
        except ValueError:
            return self._error("invalid", "invalid_command")
        rid = cmd.request_id
        payload = cmd.model_dump_json()
        with self.lock:
            old = self.db.execute(
                "SELECT payload,response FROM requests WHERE id=?", (rid,)
            ).fetchone()
            if old:
                if old[0] != payload:
                    return self._error(rid, "request_conflict")
                if old[1] is None:
                    return self._error(rid, "interrupted")
                response = json.loads(old[1])
                if response.get("session_id") == self.sid and response.get("type") != "error":
                    # Replay current state, never a stale recording/paused acknowledgement.
                    return self._snapshot(rid)
                if response.get("session_id") != self.sid:
                    return self._error(rid, "request_conflict")
                return response
            # Persist intent BEFORE the session/microphone side effect.
            self.db.execute("INSERT INTO requests VALUES(?,?,NULL)", (rid, payload))
            self.db.commit()
            if cmd.command == "status":
                if cmd.session_id not in {None, self.sid}:
                    return self._remember(rid, self._error(rid, "invalid_state"))
                return self._remember(rid, self._snapshot(rid))
            if cmd.command in {"start", "retry"}:
                valid_start = (
                    cmd.command == "start" and self.state == "idle" and cmd.session_id is None
                )
                valid_retry = (
                    cmd.command == "retry"
                    and self.state in {"idle", "error", "completed"}
                    and cmd.session_id == self.sid
                )
                if not (valid_start or valid_retry):
                    return self._remember(rid, self._error(rid, "invalid_state"))
                try:
                    row = self.backend.create(rid)
                except Exception:  # noqa: BLE001 - capture boundary; no exception payload leaks
                    return self._remember(rid, self._error(rid, "backend_unavailable"))
                if (
                    not isinstance(row, dict)
                    or type(row.get("id")) is not int
                    or row["id"] <= 0
                    or type(row.get("is_demo")) is not bool
                ):
                    return self._remember(rid, self._error(rid, "invalid_result"))
                try:
                    self.sid, self.demo, self.code = row["id"], row["is_demo"], None
                    self.state = "error"  # crash between create/start never reopens microphone
                    self._save_active()
                    if row.get("status") != "recording":
                        raise ValueError("session is not available for capture")
                    self.recorder.start(self.sid)
                    self.state = "recording"
                    self._save_active()
                except Exception:  # noqa: BLE001 - isolate capture/backend failure and persist recoverable state
                    self.recorder.abort()
                    self._fail("capture_failed")
                    return self._remember(rid, self._error(rid, "capture_failed"))
                return self._remember(rid, self._base(rid))
            if cmd.session_id != self.sid or self.sid is None:
                return self._remember(rid, self._error(rid, "invalid_state"))
            try:
                if cmd.command == "pause" and self.state == "recording":
                    self.recorder.pause()
                    self._confirm_capture("paused")
                    self.state = "paused"
                elif cmd.command == "resume" and self.state == "paused":
                    self.recorder.resume()
                    self._confirm_capture("recording")
                    self.state = "recording"
                elif cmd.command == "finish" and self.state in {"recording", "paused"}:
                    path = self.recorder.finish()
                    self.state = "processing"
                    self._save_active()
                    response = self._remember(rid, self._base(rid))
                    self.future = self.pool.submit(self._analyze, rid, self.sid, path)
                    return response
                elif cmd.command == "finish" and self.state in {"processing", "completed", "error"}:
                    return self._remember(rid, self._snapshot(rid))
                else:
                    return self._remember(rid, self._error(rid, "invalid_state"))
                self._save_active()
                return self._remember(rid, self._base(rid))
            except Exception:  # noqa: BLE001 - isolate capture/backend failure and persist recoverable state
                self.recorder.abort()
                self._fail("capture_failed")
                return self._remember(rid, self._error(rid, "capture_failed"))

    def _analyze(self, rid, sid, path):
        try:
            self.backend.upload(sid, path)
            row = self.backend.finish(sid, rid)
            with self.lock:
                if row.get("status") == "processing":
                    self.state, self.code = "processing", None
                    self._save_active()
                    response = self._base(rid)
                elif row.get("status") == "error":
                    self.state, self.code = "error", row.get("error_code") or "invalid_result"
                    self._save_active()
                    response = self._error(rid, self.code)
                else:
                    response = self._result(rid, row)
                self.events.put(self._remember(rid, response))
        except ValueError:
            with self.lock:
                self._fail("invalid_result")
                self.events.put(self._remember(rid, self._error(rid, "invalid_result")))
        except Exception:  # noqa: BLE001 - isolate capture/backend failure and persist recoverable state
            with self.lock:
                # The backend may still be processing after an HTTP timeout.
                # Keep processing and recover via GET; never issue finish again here.
                response = self._base(rid)
                self.events.put(self._remember(rid, response))

    def check_capture(self):
        with self.lock:
            if self.state in {"recording", "paused"}:
                try:
                    self.recorder.check()
                except Exception:  # noqa: BLE001 - isolate capture/backend failure and persist recoverable state
                    self.recorder.abort()
                    self._fail("capture_failed")

    def disconnect(self):
        with self.lock:
            if self.state in {"recording", "paused"}:
                self.recorder.abort()
                self._fail("disconnected")

    def drain_events(self):
        while True:
            try:
                yield self.events.get_nowait()
            except Empty:
                return

    def wait_for_analysis(self):
        if self.future:
            self.future.result(timeout=10)

    def close(self):
        self.disconnect()
        self.pool.shutdown(wait=True)
        self.db.close()

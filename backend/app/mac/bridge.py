"""Single-capture bridge with durable request receipts and async analysis."""

import json
import logging
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from queue import Empty, SimpleQueue
from threading import RLock
from time import monotonic

from app.config import get_settings
from app.mac.dialogue import (
    choose_focus,
    comparison_for,
    hint_for,
    mission_previews,
    question_for,
)
from app.mac.partials import PartialTranscriber
from app.mac.protocol import Command, validate_result
from app.services.content_matching import match_point, reference_synonyms

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
    "cancelled": "Sessao cancelada pelo operador.",
    "mission_changed": "O material mudou. Atualize as missoes antes de comecar.",
}


class MacBridge:
    def __init__(self, backend, recorder, journal_path: Path, *, speaker=None):
        self.backend, self.recorder, self.speaker = backend, recorder, speaker
        self.lock = RLock()
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(journal_path, check_same_thread=False)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, payload TEXT NOT NULL, response TEXT)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS active (id INTEGER PRIMARY KEY CHECK(id=1), session_id INTEGER, state TEXT, demo INTEGER, code TEXT)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS uploaded (session_id INTEGER NOT NULL, sequence INTEGER NOT NULL, byte_size INTEGER NOT NULL, PRIMARY KEY(session_id, sequence))"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS interaction (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)"
        )
        saved_interaction = self.db.execute("SELECT payload FROM interaction WHERE id=1").fetchone()
        try:
            self.interaction = json.loads(saved_interaction[0]) if saved_interaction else {}
            if not isinstance(self.interaction, dict):
                self.interaction = {}
        except (TypeError, ValueError):
            self.interaction = {}
        row = self.db.execute("SELECT session_id,state,demo,code FROM active WHERE id=1").fetchone()
        recorder_is_demo = bool(getattr(self.recorder, "is_demo", False))
        self.sid, self.state, self.demo, self.code = row or (
            None,
            "idle",
            recorder_is_demo,
            None,
        )
        self.demo = bool(self.demo)
        self._spoken_result_sid = self.sid if self.state == "completed" else None
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="nekomind-analysis")
        self.ops_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="nekomind-ops")
        self.future = None
        self.ops_futures = []
        self.events = SimpleQueue()
        self.diagnostics = []
        self.calibration = None
        self.epoch = 0
        self.last_ops_tick = 0.0
        self.event_rid = None
        self.journey = {}
        self.last_voice_event = 0.0
        self.ops_future = None
        self.serial_connected = False
        self.selected_content_id = None
        self.mission_content_id = None
        self.mission_points = []
        self.missions = []
        self.mission_index = 0
        self.guided_snapshot = None
        self.partial = None
        self.live_matches = []
        self.live_sequence = 0
        self.last_live_frame = 0.0
        self.live_summary = None
        self.guided_started_at = 0.0
        if self.state in {"recording", "paused"}:
            self.state, self.code = "recovery", "interrupted"
            self._save_active()
            self._mark_capture_interrupted("interrupted")
        elif self.state == "recovery" and self.code in {"disconnected", "interrupted"}:
            self._mark_capture_interrupted(self.code)
        self.db.commit()

    def _save_active(self):
        self.db.execute(
            "INSERT OR REPLACE INTO active VALUES(1,?,?,?,?)",
            (self.sid, self.state, int(self.demo), self.code),
        )
        self.db.commit()

    def _save_interaction(self):
        self.db.execute(
            "INSERT OR REPLACE INTO interaction VALUES(1,?)",
            (json.dumps(self.interaction, ensure_ascii=False),),
        )
        self.db.commit()

    def _fetch_missions(self):
        selected = getattr(self.backend, "selected_content", None)
        content = getattr(self.backend, "content", None)
        if selected is None or content is None:
            return None, []
        content_id = selected()
        if content_id is None:
            return None, []
        row = content(content_id)
        if row.get("id") != content_id or not isinstance(row.get("points"), list):
            raise ValueError("Conteudo selecionado invalido")
        points = row["points"]
        if not points or len(points) > 30 or any(
            not isinstance(point, str) or not point.strip() for point in points
        ):
            raise ValueError("Pontos preparados invalidos")
        return content_id, points

    def _set_missions(self, content_id, points):
        previews = mission_previews(points)
        if (
            content_id != self.mission_content_id
            or previews != self.missions
            or points != self.mission_points
        ):
            self.mission_index = 0
        self.mission_content_id = content_id
        self.mission_points = points
        self.missions = previews

    def _followup_wire(self):
        item = self.interaction
        if (
            self.state in {"idle", "checking", "ready"}
            or not item
            or self.sid not in {item.get("first_sid"), item.get("second_sid")}
        ):
            return None
        stage = item.get("stage")
        if stage not in {"question", "hint", "answering", "done"}:
            return None
        return {
            "stage": stage,
            "point_index": item["focus_index"],
            "question": item["question"],
            "hint": item.get("hint", "") if item.get("hint_shown") else "",
            "comparison": item.get("comparison", "") if stage == "done" else "",
        }

    def _followup_public(self):
        followup = self._followup_wire()
        if followup is not None and followup["stage"] == "done":
            followup.update(
                source_point=self.interaction.get("focus_point", ""),
                first_excerpt=self.interaction.get("first_evidence", ""),
                second_excerpt=self.interaction.get("second_evidence", ""),
            )
        return followup

    def _fail(self, code):
        self.state, self.code = "error", code
        self._save_active()
        if self.sid is not None:
            try:
                self.backend.capture_state(self.sid, "error", code)
            except Exception:  # noqa: BLE001
                logger.warning("Falha registrada no diario local; backend indisponivel.")

    def _say(self, text):
        if self.speaker is None:
            return
        try:
            self.speaker.speak(text)
        except Exception:  # noqa: BLE001 - voz opcional nao altera a captura
            logger.warning("Voz local indisponivel; mantendo o fluxo de captura.")

    def _silence(self):
        if self.speaker is None:
            return
        try:
            self.speaker.stop()
        except Exception:  # noqa: BLE001 - captura tem prioridade sobre voz
            logger.warning("Falha ao interromper a voz local.")

    def _result_speech(self, row):
        if self.demo:
            return "A demonstração terminou. Em uma sessão real, vou ouvir sua explicação."
        report = row.get("content_report")
        if isinstance(report, dict):
            coverage = report.get("coverage_percent")
            if isinstance(coverage, (int, float)) and coverage < 50:
                return "Obrigada por explicar! Quer tentar de novo e falar de outro ponto do material?"
            return "Obrigada por explicar! Quer tentar de novo e ligar duas ideias com um exemplo?"
        return "Obrigada por explicar! Quer tentar de novo e incluir um exemplo?"

    def _prepare_interaction_result(self, row):
        item = self.interaction
        if self.demo or not item:
            return None
        if self.sid == item.get("first_sid") and item.get("stage") == "explaining":
            focus = choose_focus(row.get("content_report"), item.get("mission_index", 0))
            if focus is None:
                return None
            index, point = focus
            first_match = match_point(point, row.get("transcription", ""))
            item.update(
                stage="question",
                focus_index=index,
                focus_point=point,
                question=question_for(point),
                hint=hint_for(point),
                hint_shown=False,
                first_status=first_match.status,
                first_evidence=first_match.evidence or "",
            )
            self._save_interaction()
            return item["question"]
        if self.sid == item.get("second_sid") and item.get("stage") == "answering":
            second_match = match_point(item["focus_point"], row.get("transcription", ""))
            item.update(
                stage="done",
                second_status=second_match.status,
                second_evidence=second_match.evidence or "",
                comparison=comparison_for(
                    item["focus_point"], item["first_status"], second_match.status,
                    item.get("first_evidence", ""), second_match.evidence or "",
                ),
            )
            self._save_interaction()
            return item["comparison"]
        return None

    def _base(self, rid, kind="state"):
        message = {
            "v": 1,
            "type": kind,
            "request_id": rid,
            "session_id": self.sid,
            "state": self.state,
            "is_demo": self.demo,
        }

        if self.state == "ready" and self.missions:
            message["missions"] = list(self.missions)
        followup = self._followup_wire()
        if followup is not None:
            message["followup"] = followup

        if kind == "state":
            if self.state == "recording":
                voice = self._voice()
                if voice is not None:
                    message["voice"] = voice
                message["journey"] = {"step": "capture", "status": "running"}
            elif self.state == "processing" and self.journey:
                message["journey"] = dict(self.journey)
            if self.state in {"checking", "ready", "error"} and self.diagnostics:
                component = next(
                    (c for c in self.diagnostics if c["status"] == "error"),
                    self.diagnostics[int(monotonic() / 2) % len(self.diagnostics)],
                )
                message["diagnostic"] = {
                    "component": component["component"],
                    "status": component["status"],
                }
        return message

    def _ops_snapshot(self):
        voice = self._voice()
        snapshot = {
            "session_id": self.sid,
            "state": self.state,
            "is_demo": self.demo,
            "diagnostics": list(self.diagnostics),
            "voice": voice if self.state == "recording" else None,
            "calibration": dict(self.calibration) if self.calibration is not None else None,
            "error_code": self.code,
            "missions": list(self.missions) if self.state == "ready" else [],
            "followup": self._followup_public(),
            "content": dict(self.live_summary)
            if self.state == "recording" and self.live_summary
            else None,
        }
        return snapshot

    def mark_serial_connected(self):
        self.serial_connected = True

    def mark_serial_disconnected(self):
        self.serial_connected = False

    def _voice(self):
        getter = getattr(self.recorder, "voice", None)
        if getter is None:
            return None
        try:
            return getter()
        except Exception:  # noqa: BLE001
            return {"level": 0, "clipping": False, "quality": "unknown"}

    def _error(self, rid, code):
        payload = self._base(rid, "error")
        payload.pop("missions", None)
        payload.pop("followup", None)
        return {
            **payload,
            "state": "error",
            "code": code,
            "message": MESSAGES.get(code, "Falha na sessao; confira a captura e tente novamente."),
        }

    def _snapshot(self, rid):
        if self.state == "recovery":
            return {
                **self._base(rid),
                "code": self.code or "interrupted",
                "message": MESSAGES.get(self.code or "interrupted", MESSAGES["interrupted"]),
            }
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
                if (self.future is None or self.future.done()) and row.get(
                    "status"
                ) != "processing":
                    self._fail("interrupted")
                    return self._error(rid, "interrupted")
            except ValueError:
                self._fail("invalid_result")
                return self._error(rid, "invalid_result")
            except Exception:  # noqa: BLE001
                return self._error(rid, "backend_unavailable")
        return self._base(rid)

    def _result(self, rid, row):
        validate_result(row, self.sid)
        self.state, self.demo, self.code = "completed", row["is_demo"], None
        self._save_active()
        try:
            spoken = self._prepare_interaction_result(row)
        except Exception:  # noqa: BLE001 - optional dialogue must not hide a valid result
            logger.warning("Pergunta local indisponivel; resultado preservado.")
            spoken = None
        if self._spoken_result_sid != self.sid:
            self._spoken_result_sid = self.sid
            self._say(spoken or self._result_speech(row))
        shorten = lambda text, limit: text.encode()[:limit].decode("utf-8", errors="ignore")
        response = {
            **self._base(rid, "result"),
            "asr_provider": row["asr_provider"],
            "topic_provider": row["topic_provider"],
            "topics": [shorten(t["name"], 120) for t in row["topics"][:5]],
            "summary": "Demonstracao concluida; dados simulados."
            if self.demo
            else "Funcionou! Voz captada e processada.",
        }
        report = row.get("content_report")
        if isinstance(report, dict) and report.get("content_id") == row.get("reference_content_id"):
            response["summary"] = shorten(
                f"{'Demo guiada' if self.demo else 'Material completo'}: "
                f"{report.get('coverage_percent', 0)}% dos pontos mencionados; "
                "a missao e um ponto. Nao comprova acerto.",
                220,
            )
        if self.interaction.get("stage") == "done" and self.sid == self.interaction.get(
            "second_sid"
        ):
            response["summary"] = shorten(self.interaction["comparison"], 220)
        if row.get("duration_seconds") is not None:
            response["duration_seconds"] = round(float(row["duration_seconds"]))
        if row.get("subject"):
            response["subject"] = shorten(str(row["subject"]), 80)
        if row.get("trend_text"):
            response["trend_text"] = shorten(str(row["trend_text"]), 120)
        return response

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

    def _is_ready_for_capture(self):
        return (
            self.state == "ready"
            and self.diagnostics
            and all(item.get("status") in {"ready", "skipped"} for item in self.diagnostics)
        )

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
                if cmd.command == "hint":
                    return response
                if response.get("session_id") == self.sid and response.get("type") != "error":
                    return self._snapshot(rid)
                if response.get("session_id") != self.sid:
                    return self._error(rid, "request_conflict")
                return response
            self.db.execute("INSERT INTO requests VALUES(?,?,NULL)", (rid, payload))
            self.db.commit()
            return self._handle_new(cmd)

    def _handle_new(self, cmd):
        rid = cmd.request_id
        if cmd.command == "status":
            if cmd.session_id not in {None, self.sid}:
                return self._remember(rid, self._error(rid, "invalid_state"))
            return self._remember(rid, self._snapshot(rid))
        self.event_rid = rid
        if cmd.command in {"reset", "cancel"} and self.sid is None and cmd.session_id is None:
            self.epoch += 1
            self._silence()
            self.interaction = {}
            self._save_interaction()
            self.state, self.demo, self.code = (
                "idle",
                bool(getattr(self.recorder, "is_demo", False)),
                None,
            )
            self.diagnostics, self.calibration, self.journey = [], None, {}
            self._save_active()
            return self._remember(rid, self._base(rid))
        if cmd.command in {"diagnose", "calibrate"}:
            if self.state in {"checking", "recording", "paused", "processing"}:
                return self._remember(rid, self._error(rid, "invalid_state"))
            return self._remember(rid, self._start_diagnostics(rid, cmd.command == "calibrate"))
        if cmd.command in {"start", "retry", "answer"}:
            return self._handle_start_or_retry(cmd)
        if cmd.session_id != self.sid or self.sid is None:
            return self._remember(rid, self._error(rid, "invalid_state"))
        if cmd.command == "hint":
            item = self.interaction
            if (
                self.state != "completed"
                or self.sid != item.get("first_sid")
                or item.get("stage") not in {"question", "hint"}
            ):
                return self._remember(rid, self._error(rid, "invalid_state"))
            item["stage"] = "hint"
            item["hint_shown"] = True
            self._save_interaction()
            self._say(item["hint"])
            return self._remember(rid, self._base(rid))
        try:
            if cmd.command == "pause" and self.state == "recording":
                self._stop_partials()
                self.recorder.pause()
                self._confirm_capture("paused")
                self.state = "paused"
                self._say("Tudo bem, vou esperar. Toque em continuar quando estiver pronto.")
            elif cmd.command == "resume" and self.state == "paused":
                self._silence()
                self.recorder.resume()
                self._confirm_capture("recording")
                self.state = "recording"
                self._start_partials()
            elif cmd.command == "finish" and self.state in {"recording", "paused"}:
                self._stop_partials()
                self.live_matches = []
                self.live_summary = None
                self.guided_snapshot = None
                path = self.recorder.finish()
                self.state = "processing"
                self._save_active()
                self._say("Obrigada! Vou organizar as ideias que você explicou.")
                response = self._remember(rid, self._base(rid))
                self.future = self.pool.submit(self._analyze, rid, self.sid, path, self.epoch)
                return response
            elif cmd.command == "finish" and self.state in {"processing", "completed", "error"}:
                return self._remember(rid, self._snapshot(rid))
            elif cmd.command == "recover" and self.state == "processing":
                self.state = "processing"
                self.future = self.pool.submit(self._recover_analysis, rid, self.sid, self.epoch)
            elif cmd.command == "recover" and self.state in {"error", "recovery"}:
                row = self.backend.get(self.sid)
                if row.get("status") == "completed":
                    return self._remember(rid, self._result(rid, row))
                analysis_started = any(
                    row.get("journey", {}).get(step, {}).get("status")
                    in {"running", "completed", "error"}
                    for step in ("transcription", "topics", "result")
                )
                if (
                    row.get("status") == "processing"
                    or row.get("transcription")
                    or analysis_started
                ):
                    self.state = "processing"
                    self.demo = bool(row.get("is_demo", self.demo))
                    self.future = self.pool.submit(
                        self._recover_analysis, rid, self.sid, self.epoch
                    )
                else:
                    row = self.backend.recover(self.sid, "resume", rid)
                    cursor = self._confirmed_cursor()
                    if cursor and hasattr(self.recorder, "recover"):
                        self._silence()
                        self.recorder.recover(self.sid, confirmed_bytes=cursor)
                    else:
                        self._silence()
                        self.recorder.start(self.sid)
                    self._confirm_capture("recording")
                    self.state = "recording"
                    self.demo = bool(row.get("is_demo", self.demo))
            elif cmd.command in {"discard", "cancel", "reset"}:
                self._cancel_or_reset(cmd.command)
            else:
                return self._remember(rid, self._error(rid, "invalid_state"))
            self._save_active()
            return self._remember(rid, self._base(rid))
        except Exception:  # noqa: BLE001
            self.recorder.abort()
            self._fail("capture_failed")
            return self._remember(rid, self._error(rid, "capture_failed"))

    def _handle_start_or_retry(self, cmd):
        rid = cmd.request_id
        valid_start = (
            cmd.command == "start"
            and self._is_ready_for_capture()
            and cmd.session_id in {None, self.sid}
        )
        valid_answer = (
            cmd.command == "answer"
            and self.state == "completed"
            and cmd.session_id == self.sid == self.interaction.get("first_sid")
            and self.interaction.get("stage") in {"question", "hint"}
        )
        valid_retry = (
            cmd.command == "retry"
            and self.state in {"idle", "error", "recovery", "completed"}
            and cmd.session_id == self.sid
            and bool(self.diagnostics)
            and all(item.get("status") in {"ready", "skipped"} for item in self.diagnostics)
        )
        second_retry = (
            valid_retry
            and self.interaction.get("stage") == "answering"
            and self.sid == self.interaction.get("second_sid")
        )
        if not (valid_start or valid_retry or valid_answer):
            return self._remember(rid, self._error(rid, "invalid_state"))
        mission_index = 0
        try:
            if valid_answer or second_retry:
                content_id = self.interaction["content_id"]
            elif hasattr(self.backend, "selected_content") and hasattr(self.backend, "content"):
                content_id, points = self._fetch_missions()
                previews = mission_previews(points)
                if (
                    valid_start
                    and cmd.mission_index is not None
                    and (
                        content_id != self.mission_content_id
                        or previews != self.missions
                        or points != self.mission_points
                    )
                ):
                    self._set_missions(content_id, points)
                    return self._remember(rid, self._error(rid, "mission_changed"))
                self._set_missions(content_id, points)
                if valid_start and cmd.mission_index is not None:
                    if cmd.mission_index >= len(points):
                        return self._remember(rid, self._error(rid, "invalid_state"))
                    mission_index = cmd.mission_index
            else:
                content_id = self.selected_content_id
        except Exception:  # noqa: BLE001 - never start from an unverified mission list
            return self._remember(rid, self._error(rid, "backend_unavailable"))
        # Diagnose can follow an interrupted capture. Starting a new attempt is
        # an explicit choice; close the old backend session before creating it.
        # Cancel preserves the session and its uploaded chunks for inspection.
        if self.sid is not None:
            try:
                previous = self.backend.get(self.sid)
                if previous.get("status") not in {"completed", "error", "cancelled"}:
                    self.backend.cancel(self.sid, confirmed=True)
            except Exception:  # noqa: BLE001 - do not start two active sessions
                return self._remember(rid, self._error(rid, "backend_unavailable"))
        try:
            self.selected_content_id = content_id
            try:
                if content_id is None:
                    row = self.backend.create(
                        rid, is_demo=bool(getattr(self.recorder, "is_demo", False))
                    )
                else:
                    row = self.backend.create(
                        rid,
                        is_demo=bool(getattr(self.recorder, "is_demo", False)),
                        reference_content_id=content_id,
                    )
            except TypeError:
                if content_id is not None:
                    raise
                row = self.backend.create(rid)
        except Exception:  # noqa: BLE001
            return self._remember(rid, self._error(rid, "backend_unavailable"))
        if (
            not isinstance(row, dict)
            or type(row.get("id")) is not int
            or row["id"] <= 0
            or type(row.get("is_demo")) is not bool
        ):
            return self._remember(rid, self._error(rid, "invalid_result"))
        try:
            self.epoch += 1
            self.sid, self.demo, self.code = row["id"], row["is_demo"], None
            self.state = "error"
            self._save_active()
            if row.get("status") != "recording":
                raise ValueError("session is not available for capture")
            self._silence()
            self.recorder.start(self.sid)
            self._confirm_capture("recording")
            self.state = "recording"
            if valid_answer or second_retry:
                self.interaction.update(stage="answering", second_sid=self.sid)
                self.mission_index = self.interaction["focus_index"]
            elif content_id is not None and row.get("reference_content_id") and not self.demo:
                self.mission_index = mission_index
                self.interaction = {
                    "stage": "explaining",
                    "content_id": content_id,
                    "mission_index": mission_index,
                    "first_sid": self.sid,
                }
            else:
                self.interaction = {}
            self._save_interaction()
            self.guided_snapshot = None
            self.live_matches = []
            self.live_summary = None
            self.guided_started_at = monotonic()
            if row.get("reference_content_id") and not self.demo:
                try:
                    self.guided_snapshot = self.backend.reference(self.sid)
                except Exception:  # noqa: BLE001 - optional feedback must not block capture
                    self.guided_snapshot = None
                if self.guided_snapshot is None:
                    self._set_content_unavailable()
                else:
                    self._start_partials()
            self._save_active()
        except Exception:  # noqa: BLE001
            self.recorder.abort()
            self._fail("capture_failed")
            return self._remember(rid, self._error(rid, "capture_failed"))
        return self._remember(rid, self._base(rid))

    def _cancel_or_reset(self, command):
        self.epoch += 1
        self._silence()
        self.interaction = {}
        self._save_interaction()
        self._stop_partials()
        self.guided_snapshot = None
        self.live_matches = []
        self.live_summary = None
        self.recorder.abort()
        if self.sid is not None and (
            command in {"discard", "cancel"} or self.state not in {"completed", "idle", "ready"}
        ):
            cancel = getattr(self.backend, "cancel", None)
            if cancel is not None:
                cancel(self.sid, confirmed=True)
            else:
                self.backend.capture_state(self.sid, "error", "cancelled")
            if command == "discard":
                self.backend.delete(self.sid, confirmed=True)
        self.state, self.sid, self.demo, self.code = (
            "idle",
            None,
            bool(getattr(self.recorder, "is_demo", False)),
            None,
        )
        self.diagnostics, self.calibration, self.journey = [], None, {}

    def _start_diagnostics(self, rid, calibrate):
        self.state = "checking"
        self._save_active()
        self.ops_futures.append(
            self.ops_pool.submit(self._run_diagnostics, rid, calibrate, self.epoch)
        )
        return self._base(rid)

    def _run_diagnostics(self, rid, calibrate, epoch):
        components = []
        try:
            components.extend(self.backend.readiness().get("components", []))
        except Exception:  # noqa: BLE001
            components.append(
                {"component": "backend", "status": "error", "message": "Backend indisponivel"}
            )
        probe = getattr(self.recorder, "probe", None)
        if probe is not None:
            try:
                components.extend(probe())
            except Exception:  # noqa: BLE001
                components.append(
                    {"component": "microphone", "status": "error", "message": "Falha no probe"}
                )
        else:
            status = "skipped" if self.demo else "error"
            components.append(
                {"component": "microphone", "status": status, "message": "Probe indisponivel"}
            )
        serial_status = "ready" if self.serial_connected else ("skipped" if self.demo else "error")
        components.append(
            {
                "component": "serial",
                "status": serial_status,
                "message": "Serial conectado"
                if self.serial_connected
                else "Serial dispensado em demo"
                if self.demo
                else "Serial sem mensagem valida recente",
            }
        )
        components.append(
            {
                "component": "device",
                "status": serial_status,
                "message": "Identificacao logica confirmada por comando serial"
                if self.serial_connected
                else "Dispositivo dispensado no emulador"
                if self.demo
                else "Conecte o dispositivo",
            }
        )
        calibration = self._run_calibration() if calibrate else None
        mission_content_id, mission_points = None, []
        try:
            mission_content_id, mission_points = self._fetch_missions()
        except Exception:  # noqa: BLE001 - a selected mission must be verified before capture
            components.append(
                {"component": "briefing", "status": "error", "message": "Missoes indisponiveis"}
            )
        if (
            calibration is not None
            and not calibration.get("valid")
            and calibration.get("status") != "skipped"
        ):
            components.append(
                {
                    "component": "calibration",
                    "status": "error",
                    "message": calibration.get("message", "Calibracao invalida"),
                }
            )
        state = (
            "ready" if all(c.get("status") in {"ready", "skipped"} for c in components) else "error"
        )
        with self.lock:
            if epoch != self.epoch or self.state != "checking":
                return
            self.diagnostics = components
            self.calibration = calibration
            self._set_missions(mission_content_id, mission_points)
            self.state = state
            self.code = None if state == "ready" else "capture_failed"
            self._save_active()
            self.events.put(self._base(rid))
            if state == "ready":
                self._say(
                    "Oi! Escolha uma missão na tela e toque em começar. Depois me explique "
                    "esse ponto com as suas palavras."
                    if self.missions
                    else "Oi! Sou sua gatinha de estudos. Toque em começar e me explique o tema "
                    "com as suas palavras."
                )

    def _run_calibration(self):
        runner = getattr(self.recorder, "calibrate", None)
        if runner is None:
            return {
                "status": "skipped" if self.demo else "error",
                "device_id": getattr(self.recorder, "device", None),
                "quality": "unknown",
                "message": "Calibracao indisponivel neste recorder",
                "duration_seconds": 0,
                "valid": False,
            }
        try:
            return runner()
        except Exception:  # noqa: BLE001
            return {
                "status": "error",
                "device_id": getattr(self.recorder, "device", None),
                "quality": "unknown",
                "message": "Calibracao falhou",
                "duration_seconds": 0,
                "valid": False,
            }

    def _recovery_manifest(self, sid=None):
        sid = self.sid if sid is None else sid
        getter = getattr(self.recorder, "recovery_manifest", None)
        if getter is None or self.sid is None:
            return None
        try:
            return getter(sid)
        except Exception:  # noqa: BLE001
            return None

    def _manifest_chunks(self, manifest):
        if isinstance(manifest, list):
            return list(manifest)
        if isinstance(manifest, dict):
            return list(manifest.get("chunks") or manifest.get("confirmed_chunks") or [])
        return []

    def _manifest_confirmed_bytes(self, manifest):
        if isinstance(manifest, dict) and manifest.get("confirmed_bytes") is not None:
            return int(manifest.get("confirmed_bytes") or 0)
        return sum(int(chunk["byte_size"]) for chunk in self._manifest_chunks(manifest))

    def _confirmed_cursor(self):
        manifest = self._recovery_manifest()
        if manifest:
            return self._manifest_confirmed_bytes(manifest)
        getter = getattr(self.recorder, "confirmed_chunks", None)
        if getter is None:
            return 0
        chunks = getter()
        if not chunks:
            return 0
        last = chunks[-1]
        return int(last["offset"]) + int(last["byte_size"])

    def _upload_available(self, sid):
        manifest = self._recovery_manifest(sid)
        chunks = self._manifest_chunks(manifest)
        if not chunks and hasattr(self.recorder, "confirmed_chunks"):
            chunks = list(self.recorder.confirmed_chunks())
        pending = []
        for chunk in chunks:
            sequence = int(chunk["sequence"])
            old = self.db.execute(
                "SELECT byte_size FROM uploaded WHERE session_id=? AND sequence=?",
                (sid, sequence),
            ).fetchone()
            if old and int(old[0]) == int(chunk["byte_size"]):
                continue
            pending.append(chunk)
        if pending:
            self.backend.upload_manifest(sid, pending)
            for chunk in pending:
                self.db.execute(
                    "INSERT OR REPLACE INTO uploaded VALUES(?,?,?)",
                    (sid, int(chunk["sequence"]), int(chunk["byte_size"])),
                )
            self.db.commit()
        return len(pending)

    def _final_manifest(self, sid):
        uploaded_now = self._upload_available(sid)
        chunks = []
        if hasattr(self.recorder, "final_remainder"):
            remainder = self.recorder.final_remainder()
            if remainder is not None:
                old = self.db.execute(
                    "SELECT byte_size FROM uploaded WHERE session_id=? AND sequence=?",
                    (sid, int(remainder["sequence"])),
                ).fetchone()
                if not old or int(old[0]) != int(remainder["byte_size"]):
                    chunks.append(remainder)
        uploaded_total = self.db.execute(
            "SELECT COUNT(*) FROM uploaded WHERE session_id=?", (sid,)
        ).fetchone()[0]
        return chunks, bool(uploaded_now or uploaded_total)

    def _analyze(self, rid, sid, path, epoch):
        try:
            with self.lock:
                if epoch != self.epoch or sid != self.sid:
                    return
            manifest, has_uploaded = self._final_manifest(sid)
            if manifest and hasattr(self.backend, "upload_manifest"):
                self.backend.upload_manifest(sid, manifest)
            elif not has_uploaded:
                self.backend.upload(sid, path)
            row = self.backend.finish(sid, rid)
            with self.lock:
                if epoch != self.epoch or sid != self.sid:
                    return
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
                if epoch != self.epoch or sid != self.sid:
                    return
                self._fail("invalid_result")
                self.events.put(self._remember(rid, self._error(rid, "invalid_result")))
        except Exception:  # noqa: BLE001
            with self.lock:
                if epoch != self.epoch or sid != self.sid:
                    return
                self.events.put(self._remember(rid, self._base(rid)))

    def _recover_analysis(self, rid, sid, epoch):
        try:
            row = self.backend.recover(sid, "analyze", rid)
            with self.lock:
                if epoch != self.epoch or sid != self.sid:
                    return
                if row.get("status") == "completed":
                    response = self._result(rid, row)
                elif row.get("status") == "processing":
                    response = self._base(rid)
                else:
                    self._fail("invalid_result")
                    response = self._error(rid, "invalid_result")
                self.events.put(self._remember(rid, response))
        except Exception:  # noqa: BLE001 - worker boundary must return a safe operational error
            with self.lock:
                if epoch == self.epoch and sid == self.sid:
                    self._fail("backend_unavailable")
                    self.events.put(self._error(rid, "backend_unavailable"))

    def check_capture(self):
        with self.lock:
            if self.state in {"recording", "paused"}:
                try:
                    self.recorder.check()
                except Exception:  # noqa: BLE001
                    self._stop_partials()
                    self.recorder.abort()
                    self._fail("capture_failed")

    def disconnect(self):
        with self.lock:
            self._silence()
            self._stop_partials()
            if self.state in {"recording", "paused"}:
                self.recorder.abort()
                self.state, self.code = "recovery", "disconnected"
                self._save_active()
                self._mark_capture_interrupted("disconnected")

    def _mark_capture_interrupted(self, code):
        if self.sid is None:
            return
        try:
            self.backend.capture_state(self.sid, "error", code)
        except Exception:  # noqa: BLE001 - local journal remains recoverable
            logger.warning("Captura interrompida no diario local; backend indisponivel.")

    def drain_events(self):
        while True:
            try:
                yield self.events.get_nowait()
            except Empty:
                return

    def wait_for_analysis(self):
        if self.future:
            self.future.result(timeout=10)

    def wait_for_operations(self):
        while self.ops_futures:
            self.ops_futures.pop(0).result(timeout=10)
        if self.ops_future is not None:
            self.ops_future.result(timeout=10)

    def tick(self, *, force=False):
        with self.lock:
            now = monotonic()
            if self.state == "recording" and self.event_rid and now - self.last_voice_event >= 0.2:
                self.last_voice_event = now
                event = self._base(self.event_rid)
                voice = self._voice()
                if voice is not None:
                    event["voice"] = voice
                event["journey"] = {"step": "capture", "status": "running"}
                self.events.put(event)
            if not force and now - self.last_ops_tick < 1.0:
                return
            self.last_ops_tick = now
            if self.ops_future is not None and not self.ops_future.done():
                return
            self.ops_future = self.ops_pool.submit(self._ops_tick_worker)

    def _ops_tick_worker(self):
        try:
            with self.lock:
                sid = self.sid
                state = self.state
                snapshot = self._ops_snapshot()
            if state == "recording" and sid is not None:
                self._upload_available(sid)
            published = self.backend.publish(snapshot)
            if isinstance(published, dict):
                selected = published.get("selected_content_id")
                if selected is None or type(selected) is int and selected > 0:
                    self.selected_content_id = selected
                    if state == "ready" and selected != self.mission_content_id:
                        try:
                            content_id, points = self._fetch_missions()
                        except Exception:  # noqa: BLE001 - start revalidates the selection
                            content_id, points = None, []
                        with self.lock:
                            if self.state == "ready":
                                self._set_missions(content_id, points)
                                if self.event_rid:
                                    self.events.put(self._base(self.event_rid))
            if sid and state == "processing":
                row = self.backend.get(sid)
                saved = row.get("journey") or {}
                with self.lock:
                    if sid == self.sid and self.state == "processing":
                        for step in ("result", "topics", "transcription", "capture"):
                            entry = saved.get(step, {})
                            if entry.get("status") in {"running", "error"}:
                                self.journey = {"step": step, **entry}
                                break
                        if self.event_rid:
                            if row.get("status") == "completed":
                                self.events.put(self._result(self.event_rid, row))
                            else:
                                self.events.put(self._base(self.event_rid))
            for command in self.backend.commands().get("commands", []):
                rid = command.get("request_id")
                response = self.handle(command)
                if isinstance(rid, str):
                    self.backend.ack_command(rid, response)
        except Exception:  # noqa: BLE001
            logger.warning("Operacoes do bridge indisponiveis; mantendo captura local.")

    def close(self):
        self._stop_partials()
        self.disconnect()
        self.pool.shutdown(wait=True)
        self.ops_pool.shutdown(wait=True)
        self.db.close()
        if self.speaker is not None:
            self.speaker.close()

    def _stop_partials(self):
        self.recorder.partial_sink = None
        partial, self.partial = self.partial, None
        if partial is not None:
            partial.stop()

    def _start_partials(self):
        if not self.guided_snapshot or not get_settings().guided_live_enabled or self.demo:
            return
        try:
            from app.adapters.asr_adapter import get_asr_adapter

            settings = get_settings()
            if settings.asr_provider != "faster_whisper":
                return
            adapter = get_asr_adapter(
                settings.asr_provider,
                settings.asr_model_size,
                settings.asr_device,
                settings.asr_compute_type,
            )
            epoch, sid = self.epoch, self.sid
            worker = PartialTranscriber(
                adapter,
                lambda text, latency: self._on_partial(epoch, sid, text, latency),
                interval_seconds=settings.guided_partial_interval_seconds,
                window_seconds=settings.guided_window_seconds,
            )
            self.partial = worker
            self.recorder.partial_sink = worker
            worker.start()
        except Exception:  # noqa: BLE001 - optional feedback must not stop recording
            self._stop_partials()
            self._set_content_unavailable()

    def _set_content_unavailable(self):
        self.live_sequence += 1
        self.live_summary = {
            "status": "unavailable",
            "expression": "thinking",
            "coverage_percent": 0,
            "origin": "real",
            "seq": self.live_sequence,
        }
        if self.event_rid and self.event_rid.startswith("c2-"):
            self.events.put({**self._base(self.event_rid, "content"), **self.live_summary})

    def _on_partial(self, epoch, sid, text, latency):
        with self.lock:
            if epoch != self.epoch or sid != self.sid or self.state != "recording":
                return
            if text is None:
                self._set_content_unavailable()
                return
            if (
                not text.strip()
                or self._voice()
                and self._voice().get("quality") in {"low", "clipping"}
            ):
                return
            try:
                points = self.guided_snapshot.get("points", [])
                synonyms = reference_synonyms(self.guided_snapshot.get("text", ""))
                fresh = [match_point(point, text, synonyms=synonyms) for point in points]
            except Exception:  # noqa: BLE001 - optional matcher must degrade safely
                self._set_content_unavailable()
                return
            if not self.live_matches:
                self.live_matches = fresh
            else:
                rank = {"not_mentioned": 0, "partial": 1, "covered": 2, "possible_divergence": 3}
                self.live_matches = [
                    new if rank[new.status] > rank[old.status] else old
                    for old, new in zip(self.live_matches, fresh)
                ]
            covered = sum(m.status == "covered" for m in self.live_matches)
            partial = sum(m.status == "partial" for m in self.live_matches)
            divergent = any(m.status == "possible_divergence" for m in self.live_matches)
            expression = (
                "sad"
                if divergent
                else "happy"
                if covered
                else "content"
                if partial
                else "concerned"
                if monotonic() - self.guided_started_at >= 30
                else "thinking"
            )
            self.live_sequence += 1
            self.live_summary = {
                "status": "possible_divergence"
                if divergent
                else "covered"
                if covered
                else "partial"
                if partial
                else "not_mentioned",
                "expression": expression,
                "coverage_percent": round(100 * covered / len(points)) if points else 0,
                "origin": "real",
                "seq": self.live_sequence,
            }
            now = monotonic()
            if (
                self.event_rid
                and self.event_rid.startswith("c2-")
                and now - self.last_live_frame >= 1.0 / get_settings().guided_serial_max_hz
            ):
                self.last_live_frame = now
                self.events.put({**self._base(self.event_rid, "content"), **self.live_summary})

"""One durable experience for the touch, public screen and local operator."""

import json
import math
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.connection import get_db
from app.database.models import StudySession
from app.database.operations import Experience, OperatorCommand
from app.security import require_operator

router = APIRouter(prefix="/api/v1/experience", tags=["experience"])
State = Literal[
    "idle",
    "checking",
    "ready",
    "recording",
    "paused",
    "processing",
    "completed",
    "error",
    "recovery",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Component(StrictModel):
    component: str = Field(min_length=1, max_length=40)
    status: Literal["ready", "error", "pending", "skipped"]
    message: str = Field(default="", max_length=240)


class Voice(StrictModel):
    level: StrictInt = Field(ge=0, le=100)
    clipping: StrictBool
    quality: Literal["ok", "low", "clipping", "unknown", "noise"] = "unknown"


class BridgeUpdate(StrictModel):
    session_id: StrictInt | None = Field(default=None, gt=0)
    state: State
    is_demo: StrictBool
    diagnostics: list[Component] = Field(default_factory=list, max_length=12)
    voice: Voice | None = None
    calibration: dict | None = None
    error_code: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{0,63}$")


class CommandRequest(StrictModel):
    request_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    session_id: StrictInt | None = Field(default=None, gt=0)
    command: Literal[
        "start",
        "pause",
        "resume",
        "finish",
        "retry",
        "status",
        "diagnose",
        "calibrate",
        "recover",
        "discard",
        "cancel",
        "reset",
    ]
    confirmed: StrictBool = False
    mode: Literal["normal", "fair"] | None = None
    generation: StrictInt | None = Field(default=None, ge=0)


class Acknowledgement(StrictModel):
    response: dict


def _load(db: Session, *, create=True) -> tuple[Experience, dict]:
    row = db.get(Experience, 1)
    if row is None:
        # Called inside BEGIN IMMEDIATE for writes, preventing duplicate singleton creation.
        row = Experience(id=1, payload="{}")
        if create:
            db.add(row)
            db.flush()
    state = json.loads(row.payload)
    defaults = {
        "generation": 0,
        "session_id": None,
        "state": "idle",
        "experience_mode": "normal",
        "heartbeat": 0,
        "activity": time.time(),
        "diagnostics": [],
        "voice": None,
        "calibration": None,
        "closed": [],
        "error_code": None,
    }
    return row, {**defaults, **state}


def _save(db, row, state):
    row.payload = json.dumps(state, ensure_ascii=False)
    db.commit()


def _transaction(db):
    db.execute(text("BEGIN IMMEDIATE"))


def _status(row):
    return getattr(row.status, "value", row.status)


def _valid_result(row):
    return (
        _status(row) == "completed"
        and not row.deletion_pending
        and bool(row.transcription)
        and bool(row.asr_provider_used)
        and bool(row.topic_provider_used)
        and (row.is_demo or (row.asr_provider_used != "mock" and row.topic_provider_used != "mock"))
    )


def _wire(cmd):
    return {
        "v": 1,
        "type": "command",
        "request_id": cmd.request_id,
        "session_id": cmd.session_id,
        "command": cmd.command,
    }


def _enqueue(db, cmd):
    payload = cmd.model_dump_json()
    previous = db.get(OperatorCommand, cmd.request_id)
    if previous:
        previous_cmd = CommandRequest.model_validate_json(previous.payload)
        if previous_cmd.model_dump(exclude={"generation"}) != cmd.model_dump(
            exclude={"generation"}
        ):
            raise HTTPException(409, "request_id ja usado com outro comando.")
        return previous
    previous = OperatorCommand(request_id=cmd.request_id, payload=payload)
    db.add(previous)
    db.flush()
    return previous


def _safe_calibration(value):
    if value is None:
        return None
    # Explicit allowlist: never forward capture buffers, paths or transcripts.
    allowed = {"status", "device_id", "quality", "message", "duration_seconds", "valid"}
    result = {
        k: v for k, v in value.items() if k in allowed and isinstance(v, (str, int, float, bool))
    }
    if any(isinstance(v, str) and len(v) > 240 for v in result.values()):
        raise HTTPException(422, "Calibracao excede o limite.")
    if any(isinstance(v, float) and not math.isfinite(v) for v in result.values()):
        raise HTTPException(422, "Calibracao invalida.")
    return result


@router.post("/bridge", dependencies=[Depends(require_operator)])
def publish_bridge(payload: BridgeUpdate, db: Session = Depends(get_db)):
    _transaction(db)
    record, state = _load(db)
    sid = payload.session_id
    session = db.get(StudySession, sid) if sid else None
    if sid and (session is None or sid in state["closed"]):
        raise HTTPException(409, "Sessao ausente ou encerrada nesta experiencia.")
    if sid and state["session_id"] not in {None, sid}:
        old = db.get(StudySession, state["session_id"])
        if old is not None and (
            _status(old) not in {"completed", "error", "cancelled"} or sid <= old.id
        ):
            raise HTTPException(409, "Outra sessao controla a experiencia.")
        state["closed"] = (state["closed"] + [state["session_id"]])[-1000:]
        state["generation"] += 1
    if sid is None and payload.state == "idle" and state["session_id"] is not None:
        state["closed"] = (state["closed"] + [state["session_id"]])[-1000:]
        state["generation"] += 1
    if payload.state == "completed" and (session is None or not _valid_result(session)):
        raise HTTPException(409, "Resultado persistido ainda nao confirmado.")
    if payload.state in {"recording", "paused"} and (
        session is None or _status(session) != payload.state
    ):
        raise HTTPException(409, "Captura nao reconciliada com a sessao.")
    if payload.state != state["state"] or sid != state["session_id"]:
        state["activity"] = time.time()
    state.update(
        session_id=sid,
        state=payload.state,
        heartbeat=time.time(),
        diagnostics=[c.model_dump() for c in payload.diagnostics],
        calibration=_safe_calibration(payload.calibration),
        error_code=payload.error_code,
        voice=payload.voice.model_dump()
        if payload.voice and payload.state == "recording"
        else None,
    )
    _schedule_fair_reset(db, state)
    _save(db, record, state)
    return {"accepted": True, "generation": state["generation"]}


def _schedule_fair_reset(db, state):
    if (
        state["experience_mode"] == "fair"
        and state["state"] in {"ready", "completed", "error", "recovery"}
        and time.time() - state["activity"] > get_settings().fair_idle_seconds
    ):
        rid = f"idle-reset-{state['generation']}"
        _enqueue(
            db,
            CommandRequest(
                request_id=rid,
                command="reset",
                session_id=state["session_id"],
                confirmed=True,
                generation=state["generation"],
            ),
        )


def _snapshot(db, *, private=False):
    _, state = _load(db, create=False)
    connected = time.time() - state["heartbeat"] < get_settings().bridge_timeout_seconds
    session = db.get(StudySession, state["session_id"]) if state["session_id"] else None
    # A pure projection: a public GET never writes or schedules commands.
    if state["session_id"] is not None and session is None:
        state.update(session_id=None, state="idle", voice=None, generation=state["generation"] + 1)
    effective = state["state"]
    error = (
        {"code": state["error_code"], "message": _public_error(state["error_code"])}
        if state["error_code"]
        else None
    )
    result = None
    journey = []
    if session:
        status = _status(session)
        if status in {"processing", "error", "recovery"}:
            effective = status
        if status == "completed":
            if _valid_result(session):
                effective = "completed"
                result = {
                    "summary": "Demonstracao: dados simulados."
                    if session.is_demo
                    else (
                        "Voz captada e processada."
                        if state["experience_mode"] == "fair"
                        else "Assuntos identificados; nao comprova acerto ou dominio."
                    ),
                    "topics": [t.name for t in session.topics],
                    "duration_seconds": session.duration_seconds,
                    "clarity_score": session.clarity_score,
                    "subject": getattr(session, "subject", None),
                    "metric_method_version": getattr(
                        session, "metric_method_version", "heuristic-v1"
                    ),
                    "trend": None,
                    "asr_provider": session.asr_provider_used,
                    "topic_provider": session.topic_provider_used,
                }
                if getattr(session, "subject_confirmed", False) and result["subject"]:
                    from app.services.session_lifecycle import subject_history

                    history = subject_history(db, result["subject"])
                    result["trend"] = {
                        key: history.get(key) for key in ("trend", "method_version", "disclaimer")
                    }
            else:
                effective = "error"
                error = {"code": "invalid_result", "message": "Resultado ainda nao validado."}
        try:
            saved = json.loads(getattr(session, "journey_json", "{}") or "{}")
            journey = (
                saved
                if isinstance(saved, list)
                else [
                    dict(step=k, **saved[k])
                    for k in ("capture", "transcription", "topics", "result")
                    if k in saved and isinstance(saved[k], dict)
                ]
            )
        except (TypeError, ValueError):
            journey = []
        if result is not None:
            result["evidence"] = _result_evidence(session, journey)
        if session.error_code:
            error = {"code": session.error_code, "message": _public_error(session.error_code)}
    if not connected and effective in {"recording", "paused"}:
        effective = "recovery"
        error = {
            "code": "bridge_disconnected",
            "message": "Conexao perdida. Confira o Mac para retomar.",
        }
    if not connected and effective in {"ready", "checking"}:
        effective = "error"
        error = {
            "code": "bridge_unavailable",
            "message": "Inicie ou reconecte o componente de captura no Mac.",
        }
    mode = session.mode if session else get_settings().mode
    out = {
        "schema_version": 1,
        "generation": state["generation"],
        "session_id": state["session_id"],
        "state": effective,
        "mode": mode,
        "is_demo": bool(session.is_demo) if session else mode == "demo",
        "experience_mode": state["experience_mode"],
        "diagnostics": state["diagnostics"]
        if private
        else _public_diagnostics(state["diagnostics"]),
        "journey": _public_journey(journey),
        "voice": state["voice"] if effective == "recording" else None,
        "result": result,
        "error": error,
        "recovery": effective == "recovery",
        "calibration": state["calibration"]
        if private
        else _public_calibration(state["calibration"]),
        "bridge_connected": connected,
    }
    if private:
        out["available_actions"] = [
            "diagnose",
            "calibrate",
            "cancel",
            "recover",
            "discard",
            "reset",
        ]
        out["recoverable_sessions"] = [
            {"id": s.id, "status": _status(s), "is_demo": s.is_demo, "error_code": s.error_code}
            for s in db.scalars(
                select(StudySession).where(StudySession.status.in_(["recovery", "error"])).limit(30)
            )
        ]
    return out


def _result_evidence(session, journey):
    from app.services.clarity_evaluation import word_count

    try:
        validation = json.loads(session.audio_validation or "{}")
    except (TypeError, ValueError):
        validation = {}
    speech_seconds = validation.get("speech_seconds", 0) if isinstance(validation, dict) else 0
    speech_detected = (
        not session.is_demo
        and isinstance(speech_seconds, (int, float))
        and not isinstance(speech_seconds, bool)
        and speech_seconds > 0
    )
    completed_steps = sum(
        1 for step in journey if isinstance(step, dict) and step.get("status") == "completed"
    )
    return {
        "speech_detected": speech_detected,
        "recognized_word_count": word_count(session.transcription or ""),
        "completed_steps": min(completed_steps, 4),
        "local_processing": (
            not session.is_demo
            and session.asr_provider_used == "faster_whisper"
            and session.topic_provider_used == "local_keywords"
        ),
    }


def _public_diagnostics(items):
    messages = {
        "ready": "Disponivel.",
        "error": "Confira este componente no Mac.",
        "pending": "Aguardando verificacao.",
        "skipped": "Dispensado neste modo.",
    }
    components = {
        "backend",
        "microphone",
        "permission",
        "capture",
        "serial",
        "device",
        "asr",
        "topics",
        "model",
        "calibration",
    }
    return [
        {
            "component": c["component"] if c["component"] in components else "component",
            "status": c["status"],
            "message": messages.get(c["status"], "Verifique no Mac."),
        }
        for c in items
        if isinstance(c, dict) and c.get("status") in messages
    ]


def _public_calibration(value):
    if value is None:
        return None
    quality = value.get("quality", "unknown")
    messages = {
        "ok": "Microfone calibrado.",
        "low": "Aproxime-se do microfone.",
        "clipping": "Afaste-se um pouco.",
        "noise": "Reduza o ruido ao redor.",
        "no_speech": "Fale uma frase e tente novamente.",
    }
    return {
        "status": value.get("status")
        if value.get("status") in {"ready", "error", "pending", "skipped"}
        else "pending",
        "quality": quality if quality in messages else "unknown",
        "message": messages.get(quality, "Confira a calibracao no Mac."),
        "valid": value.get("valid") is True,
    }


def _public_journey(items):
    providers = {
        "mock",
        "faster_whisper",
        "local_keywords",
        "mac_microphone",
        "synthetic",
        "heuristic-v1",
        "local",
        "mac",
        "backend",
    }
    result = []
    for entry in items:
        if not isinstance(entry, dict) or entry.get("step") not in {
            "capture",
            "transcription",
            "topics",
            "result",
        }:
            continue
        status = entry.get("status", "waiting")
        duration = entry.get("duration_ms", 0)
        result.append(
            {
                "step": entry["step"],
                "status": status
                if status in {"waiting", "running", "completed", "skipped", "error"}
                else "error",
                "duration_ms": max(0, duration) if type(duration) is int else 0,
                "provider": entry.get("provider") if entry.get("provider") in providers else None,
                "is_demo": entry.get("is_demo") is True,
            }
        )
    return result


def _public_error(code):
    return {
        "audio_unusable": "Confira a voz e o microfone; tente novamente.",
        "backend_restarted": "Sessao interrompida. Retome ou descarte.",
        "capture_failed": "Confira permissao e dispositivo do microfone.",
        "disconnected": "Reconecte o dispositivo ao Mac.",
    }.get(code, "A sessao precisa de atencao. Confira o painel do apresentador.")


@router.get("/public")
def public_snapshot(db: Session = Depends(get_db)):
    return _snapshot(db)


@router.get("/presenter", dependencies=[Depends(require_operator)])
def presenter_snapshot(db: Session = Depends(get_db)):
    return _snapshot(db, private=True)


@router.post("/commands", dependencies=[Depends(require_operator)])
def queue_command(payload: CommandRequest, db: Session = Depends(get_db)):
    if payload.command in {"reset", "cancel", "discard"} and not payload.confirmed:
        raise HTTPException(409, "Confirme a acao antes de continuar.")
    _transaction(db)
    record, state = _load(db)
    old = db.get(OperatorCommand, payload.request_id)
    if old is None and payload.session_id != state["session_id"]:
        raise HTTPException(409, "Sessao mudou; atualize o painel.")
    if old is None and payload.generation not in {None, state["generation"]}:
        raise HTTPException(409, "Experiencia mudou; atualize o painel.")
    payload = payload.model_copy(update={"generation": state["generation"]})
    receipt = _enqueue(db, payload)
    if payload.mode:
        state["experience_mode"] = payload.mode
    state["activity"] = time.time()
    _save(db, record, state)
    return {"request_id": receipt.request_id, "accepted": True}


@router.get("/commands", dependencies=[Depends(require_operator)])
def poll_commands(db: Session = Depends(get_db)):
    commands = db.scalars(
        select(OperatorCommand).where(OperatorCommand.status == "pending").limit(20)
    )
    return {"commands": [_wire(CommandRequest.model_validate_json(c.payload)) for c in commands]}


@router.get("/commands/{request_id}", dependencies=[Depends(require_operator)])
def command_receipt(request_id: str, db: Session = Depends(get_db)):
    item = db.get(OperatorCommand, request_id)
    if item is None:
        raise HTTPException(404, "Comando ausente.")
    return {
        "request_id": item.request_id,
        "status": item.status,
        "response": json.loads(item.response) if item.response else None,
    }


@router.post("/commands/{request_id}/ack", dependencies=[Depends(require_operator)])
def acknowledge(request_id: str, payload: Acknowledgement, db: Session = Depends(get_db)):
    _transaction(db)
    item = db.get(OperatorCommand, request_id)
    if item is None:
        raise HTTPException(404, "Comando ausente.")
    response = payload.response
    if (
        len(json.dumps(response)) > 8192
        or response.get("request_id") != request_id
        or (response.get("type") not in {"state", "result", "error"})
    ):
        raise HTTPException(422, "Confirmacao invalida.")
    if item.status != "pending":
        return {"accepted": True}
    cmd = CommandRequest.model_validate_json(item.payload)
    record, state = _load(db)
    if cmd.command in {"reset", "cancel", "discard"} and response.get("state") == "idle":
        if response.get("session_id") is not None:
            raise HTTPException(422, "Estado idle deve confirmar ausencia de sessao ativa.")
        already_cleared = (
            state["session_id"] is None
            and state["state"] == "idle"
            and cmd.session_id in state["closed"]
            and cmd.generation is not None
            and state["generation"] == cmd.generation + 1
        )
        if not already_cleared and (
            state["session_id"] != cmd.session_id
            or cmd.generation not in {None, state["generation"]}
        ):
            item.status = "superseded"
            db.commit()
            raise HTTPException(409, "Confirmacao pertence a experiencia anterior.")
        if state["session_id"]:
            state["closed"] = (state["closed"] + [state["session_id"]])[-1000:]
        increment = int(state["session_id"] is not None or state["state"] != "idle")
        state.update(
            session_id=None,
            state="idle",
            generation=state["generation"] + increment,
            voice=None,
            activity=time.time(),
        )
        # Older unacknowledged commands must not run for the next visitor.
        db.query(OperatorCommand).filter(
            OperatorCommand.status == "pending", OperatorCommand.request_id != request_id
        ).update({"status": "superseded"})
    item.response = json.dumps(
        {
            k: response[k]
            for k in ("request_id", "session_id", "type", "state", "code")
            if k in response
        }
    )
    item.status = "done"
    _save(db, record, state)
    return {"accepted": True}


@router.get("/providers", dependencies=[Depends(require_operator)])
def providers():
    from app.adapters.asr_adapter import get_asr_adapter
    from app.services.topic_extraction import extract_topics_result

    settings = get_settings()
    components = [{"component": "backend", "status": "ready", "message": "Backend respondeu."}]
    if settings.asr_provider == "mock":
        components.append(
            {"component": "asr", "status": "skipped", "message": "ASR demonstrativo identificado."}
        )
    else:
        try:
            get_asr_adapter(
                settings.asr_provider,
                settings.asr_model_size,
                settings.asr_device,
                settings.asr_compute_type,
            ).check_available()
            components.append(
                {"component": "asr", "status": "ready", "message": "Modelo local carregado."}
            )
        except Exception:  # noqa: BLE001 - native model boundary, sanitize paths and payload
            components.append(
                {
                    "component": "asr",
                    "status": "error",
                    "message": "Instale faster-whisper e disponibilize o modelo local configurado.",
                }
            )
    try:
        output = extract_topics_result(
            "Fotossintese transforma energia luminosa.", provider=settings.llm_provider
        )
        components.append(
            {
                "component": "topics",
                "status": "skipped" if output.is_demo else "ready",
                "message": f"Extrator: {output.provider}.",
            }
        )
    except Exception:  # noqa: BLE001 - adapter boundary, never disclose transcript/payload
        components.append(
            {"component": "topics", "status": "error", "message": "Confira o extrator configurado."}
        )
    return {"components": components}

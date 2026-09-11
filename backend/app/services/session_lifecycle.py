"""Session recovery, deletion and subject history services."""

from __future__ import annotations

import json
import shutil
import sqlite3
import threading
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.models import AudioChunk, Metric, SessionStatus, StudySession, Topic
from app.repositories.session_repository import SessionRepository
from app.services import session_analysis


class LifecycleRejectedError(ValueError):
    """Raised when a lifecycle action would violate session safety."""


# Bounded locks serialize retries in this process without retaining user data.
_delete_locks = tuple(threading.RLock() for _ in range(32))


def recover_session(
    db: Session,
    sid: int,
    action: str,
    request_id: str | None = None,
) -> StudySession | None:
    repo = SessionRepository(db)
    session = repo.get(sid)
    if session is None:
        return None
    if action == "resume":
        updated = (
            db.query(StudySession)
            .filter(
                StudySession.id == sid,
                StudySession.status.in_(
                    {SessionStatus.recovery, SessionStatus.error, SessionStatus.paused}
                ),
                StudySession.deletion_pending.is_(False),
            )
            .update(
                {"status": SessionStatus.paused, "error_code": None, "error_message": None},
                synchronize_session=False,
            )
        )
        db.commit()
        db.expire_all()
        if updated != 1:
            raise LifecycleRejectedError("Sessao nao esta recuperavel")
        return repo.get(sid)
    if action == "discard":
        if session.status in {SessionStatus.recording, SessionStatus.processing}:
            raise LifecycleRejectedError("Sessao ativa nao pode ser descartada sem cancelamento")
        delete_session(db, sid, confirmed=True, allow_active=True)
        return None
    if action == "analyze":
        if session.deletion_pending:
            raise LifecycleRejectedError("Sessao marcada para exclusao")
        if (
            session.status == SessionStatus.completed
            and session.error_code == "audio_cleanup_failed"
        ):
            remove_raw_audio_after_success(db, session)
            session.error_code = None
            session.error_message = None
            return repo.save(session)
        if session.status in {SessionStatus.processing, SessionStatus.completed}:
            return session
        if session.status not in {
            SessionStatus.error,
            SessionStatus.recovery,
            SessionStatus.paused,
        }:
            raise LifecycleRejectedError("Sessao nao permite retomar analise")
        if request_id and session.request_id == request_id:
            return session
        if request_id:
            session.request_id = request_id
        session.error_code = None
        session.error_message = None
        repo.save(session)
        refreshed = repo.get(sid)
        if refreshed is None:
            return None
        return session_analysis.analyze_session(
            db,
            refreshed,
            finish_request_id=request_id,
            retry_recovery=True,
        )
    raise LifecycleRejectedError("Acao de recuperacao invalida")


def delete_session(
    db: Session,
    sid: int,
    confirmed: bool,
    *,
    allow_active: bool = False,
) -> dict:
    with _delete_locks[sid % len(_delete_locks)]:
        return _delete_session_locked(db, sid, confirmed, allow_active=allow_active)


def _delete_session_locked(db: Session, sid: int, confirmed: bool, *, allow_active: bool) -> dict:
    if not confirmed:
        raise LifecycleRejectedError("Confirmacao obrigatoria para excluir sessao")
    repo = SessionRepository(db)
    existing = db.get(StudySession, sid)
    if existing is None:
        return {"session_id": sid, "deleted": False, "files_removed": 0}
    active = {
        SessionStatus.recording,
        SessionStatus.paused,
        SessionStatus.processing,
        SessionStatus.recovery,
    }
    if not allow_active and existing.status in active:
        raise LifecycleRejectedError(
            "Sessao ativa ou recuperavel nao pode ser excluida por esta rota"
        )
    if allow_active and existing.status == SessionStatus.processing:
        raise LifecycleRejectedError("Analise em andamento nao pode ser excluida por esta rota")

    allowed = {SessionStatus.completed, SessionStatus.error, SessionStatus.cancelled}
    if allow_active:
        allowed.add(SessionStatus.recovery)
    # A prior partial failure deliberately leaves the tombstone. Retrying only
    # cleanup is safe: processing claims exclude every tombstoned session.
    session = (
        existing
        if existing.deletion_pending and existing.status in allowed
        else repo.claim_deletion(sid, allowed_statuses=allowed)
    )
    if session is None:
        current = db.get(StudySession, sid)
        if current is None:
            return {"session_id": sid, "deleted": False, "files_removed": 0}
        raise LifecycleRejectedError("Sessao mudou de estado; atualize antes de excluir")

    files_removed = _remove_session_files(db, sid)
    _scrub_mac_journal(sid)
    receipts_removed = _remove_session_receipts(db, sid)
    db.delete(session)
    db.commit()
    _remove_session_dir(sid)
    return {
        "session_id": sid,
        "deleted": True,
        "files_removed": files_removed,
        "receipts_removed": receipts_removed,
    }


def set_subject(db: Session, sid: int, subject: str | None, confirmed: bool) -> StudySession | None:
    session = SessionRepository(db).get(sid)
    if session is None:
        return None
    normalized = " ".join(subject.split()) if subject else None
    session.subject = normalized
    session.subject_confirmed = bool(confirmed and normalized)
    return SessionRepository(db).save(session)


def subject_history(db: Session, subject: str, method_version: str | None = None) -> dict:
    normalized = " ".join(subject.split())
    sessions = (
        db.query(StudySession)
        .filter(
            func.lower(StudySession.subject) == normalized.lower(),
            StudySession.subject_confirmed.is_(True),
            StudySession.status == SessionStatus.completed,
            StudySession.deletion_pending.is_(False),
        )
        .order_by(StudySession.ended_at.asc(), StudySession.id.asc())
        .all()
    )
    if not sessions:
        return {
            "subject": normalized,
            "method_version": "heuristic-v1",
            "disclaimer": _history_disclaimer(),
            "points": [],
            "trend": None,
        }
    versions = sorted(
        {s.metric_method_version for s in sessions},
        key=lambda version: max(s.id for s in sessions if s.metric_method_version == version),
        reverse=True,
    )
    selected_version = method_version or versions[0]
    comparable = [s for s in sessions if s.metric_method_version == selected_version]
    points = [_history_point(db, s) for s in comparable]
    return {
        "subject": normalized,
        "method_version": selected_version,
        "available_method_versions": versions,
        "disclaimer": _history_disclaimer(),
        "points": points,
        "trend": _trend(points),
    }


def remove_raw_audio_after_success(db: Session, session: StudySession) -> int:
    if getattr(get_settings(), "retain_raw_audio", False):
        return 0
    return _remove_session_files(db, session.id)


def _remove_session_files(db: Session, sid: int) -> int:
    removed = 0
    chunks = db.query(AudioChunk).filter(AudioChunk.session_id == sid).all()
    for chunk in chunks:
        path = Path(chunk.file_path)
        removed += _safe_unlink(path, _allowed_delete_roots(sid))
    for directory in _session_directories(sid):
        removed += _remove_directory_contents(directory, _allowed_delete_roots(sid), sid)
    return removed


def _remove_session_dir(sid: int) -> None:
    for session_dir in _session_directories(sid):
        if session_dir.exists() and not any(session_dir.iterdir()):
            shutil.rmtree(session_dir, ignore_errors=True)


def _session_directories(sid: int) -> list[Path]:
    settings = get_settings()
    mac_dir = Path(settings.mac_directory)
    return [
        settings.storage_dir / f"session_{sid}",
        mac_dir / "capture",
        mac_dir / "checkpoint",
        mac_dir / "manifest",
        mac_dir / f"session_{sid}",
    ]


def _allowed_delete_roots(sid: int) -> list[Path]:
    settings = get_settings()
    storage = settings.storage_dir.resolve()
    mac = Path(settings.mac_directory).resolve()
    roots = [
        storage / f"session_{sid}",
        mac / "capture",
        mac / "checkpoint",
        mac / "manifest",
        mac / f"session_{sid}",
    ]
    for root in roots:
        if root.is_symlink():
            raise LifecycleRejectedError("Diretorio de audio nao pode ser link simbolico")
    return roots


def _remove_directory_contents(directory: Path, allowed_roots: list[Path], sid: int) -> int:
    if directory.is_symlink():
        raise LifecycleRejectedError("Diretorio de audio nao pode ser link simbolico")
    if not directory.exists():
        return 0
    removed = 0
    for path in sorted(_session_paths_in_directory(directory, sid), reverse=True):
        if path.is_dir() and not path.is_symlink():
            try:
                path.rmdir()
            except OSError:
                pass
            continue
        removed += _safe_unlink(path, allowed_roots)
    return removed


def _session_paths_in_directory(directory: Path, sid: int) -> list[Path]:
    if directory.name.startswith("session_"):
        return list(directory.rglob("*"))
    paths = []
    for pattern in (
        "capture_*.raw",
        "capture_*.checkpoint",
        "capture_*.manifest",
        "*.json",
        ".capture_*.tmp",
    ):
        paths.extend(directory.glob(pattern))
    return [p for p in paths if _extract_sid(p.name) == sid]


def _extract_sid(name: str) -> int | None:
    digits = ""
    marker = "capture_"
    if marker in name:
        tail = name.split(marker, 1)[1]
        for char in tail:
            if char.isdigit():
                digits += char
            else:
                break
    return int(digits) if digits else None


def _safe_unlink(path: Path, allowed_roots: list[Path]) -> int:
    if not path.exists() and not path.is_symlink():
        return 0
    resolved = path.resolve(strict=False)
    if not any(resolved == root or root in resolved.parents for root in allowed_roots):
        raise LifecycleRejectedError("Caminho de audio fora do diretorio da sessao")
    if path.is_symlink() or any(
        parent.is_symlink()
        for parent in path.parents
        if parent.name.startswith("session_")
        or parent.name in {"capture", "checkpoint", "manifest"}
    ):
        raise LifecycleRejectedError("Caminho de audio nao pode ser link simbolico")
    if path.is_dir() and not path.is_symlink():
        return 0
    try:
        path.unlink()
    except OSError as exc:
        raise LifecycleRejectedError("Falha ao remover arquivo de audio da sessao") from exc
    return 1


def _remove_session_receipts(db: Session, sid: int) -> int:
    try:
        from app.api.routes_experience import CommandRequest
        from app.database.operations import OperatorCommand
    except ImportError:
        return 0
    removed = 0
    for item in db.query(OperatorCommand).all():
        try:
            command = CommandRequest.model_validate_json(item.payload)
        except ValidationError:
            continue
        if command.session_id == sid and item.status != "pending":
            db.delete(item)
            removed += 1
            continue
        if _response_mentions_session(item.response, sid):
            item.response = None
    return removed


def _scrub_mac_journal(sid: int) -> None:
    """Remove result content but retain command identity against retransmission."""
    path = Path(get_settings().mac_directory) / "journal.db"
    if path.is_symlink():
        raise LifecycleRejectedError("Journal nao pode ser link simbolico")
    if not path.exists():
        return
    try:
        with sqlite3.connect(f"{path.resolve().as_uri()}?mode=rw", uri=True, timeout=2) as journal:
            for rid, payload, response in journal.execute(
                "SELECT id,payload,response FROM requests"
            ):
                if _response_mentions_session(payload, sid) or _response_mentions_session(
                    response, sid
                ):
                    tombstone = json.dumps(
                        {
                            "v": 1,
                            "type": "error",
                            "request_id": rid,
                            "session_id": sid,
                            "state": "error",
                            "code": "session_deleted",
                            "message": "Sessao excluida.",
                        }
                    )
                    journal.execute("UPDATE requests SET response=? WHERE id=?", (tombstone, rid))
            journal.execute(
                "UPDATE active SET session_id=NULL,state='idle',code=NULL WHERE session_id=?",
                (sid,),
            )
    except (sqlite3.Error, OSError) as exc:
        raise LifecycleRejectedError(
            "Falha ao limpar recibos locais; tente excluir novamente"
        ) from exc


def _response_mentions_session(response: str | None, sid: int) -> bool:
    if not response:
        return False
    try:
        parsed = json.loads(response)
    except ValueError:
        return False
    return isinstance(parsed, dict) and parsed.get("session_id") == sid


def _history_point(db: Session, session: StudySession) -> dict:
    metrics = {
        metric.name: metric.value
        for metric in db.query(Metric).filter(Metric.session_id == session.id).all()
    }
    topics = [topic.name for topic in db.query(Topic).filter(Topic.session_id == session.id).all()]
    return {
        "session_id": session.id,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "duration_seconds": session.duration_seconds,
        "clarity_score": session.clarity_score,
        "topic_count": metrics.get("topic_count", float(len(topics))),
        "topics": topics,
    }


def _trend(points: list[dict]) -> dict | None:
    if len(points) < 2:
        return None
    first, last = points[0], points[-1]
    return {
        "duration_seconds_delta": _delta(
            first.get("duration_seconds"), last.get("duration_seconds")
        ),
        "clarity_score_delta": _delta(first.get("clarity_score"), last.get("clarity_score")),
        "topic_count_delta": _delta(first.get("topic_count"), last.get("topic_count")),
    }


def _delta(first: float | None, last: float | None) -> float | None:
    if first is None or last is None:
        return None
    return round(float(last) - float(first), 2)


def _history_disclaimer() -> str:
    return (
        "Tendencia local entre sessoes do mesmo assunto e metodo; "
        "nao e prova de dominio ou correcao."
    )

"""Orquestracao da analise de uma sessao ao ser finalizada.

Pipeline: junta o audio -> transcreve (ASR) -> extrai topicos (LLM) ->
calcula metricas heuristicas -> persiste tudo e fecha a sessao.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.models import SessionStatus, StudySession
from app.repositories.metric_repository import MetricRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.topic_repository import TopicRepository
from app.services import (
    audio_processing,
    clarity_evaluation,
    journey,
    topic_extraction,
    transcription,
)


class AnalysisRejectedError(RuntimeError):
    """Raised when a session cannot be evaluated without a false conclusion."""


def analyze_session(
    db: Session,
    session: StudySession,
    *,
    finish_request_id: str | None = None,
    retry_recovery: bool = False,
) -> StudySession:
    """Executa o pipeline completo e atualiza a sessao no banco."""
    session_repo = SessionRepository(db)
    from_statuses = None
    if retry_recovery:
        from_statuses = {SessionStatus.error, SessionStatus.recovery, SessionStatus.paused}
    claimed = session_repo.claim_processing(session.id, finish_request_id, from_statuses)
    if claimed is None:
        return session_repo.get(session.id) or session
    if claimed.status != SessionStatus.processing:
        return claimed
    return _analyze_session_claimed(db, claimed)


def _analyze_session_claimed(
    db: Session,
    session: StudySession,
) -> StudySession:
    settings = get_settings()
    session_repo = SessionRepository(db)
    topic_repo = TopicRepository(db)
    metric_repo = MetricRepository(db)
    asr_provider = session.asr_provider_config or settings.asr_provider
    topic_provider = session.topic_provider_config or settings.llm_provider

    try:
        _raise_if_deleting(db, session)
        duration = audio_processing.estimate_duration_seconds(db, session.id)
        wav = (
            None if session.transcription else audio_processing.merge_session_audio(db, session.id)
        )
        journey.save_step(
            session,
            "capture",
            status="completed",
            duration_ms=int(duration * 1000),
            provider=session.capture_source,
            is_demo=session.capture_source == "synthetic",
        )
        session_repo.save(session)

        real_transcription = session.mode == "real" or asr_provider != "mock"
        if real_transcription and not session.transcription:
            try:
                validation = audio_processing.validate_speech(wav)
                session.audio_validation = json.dumps(validation, ensure_ascii=False)
            except ValueError:
                _reject_analysis(
                    session_repo,
                    session,
                    "audio_unusable",
                    "Audio sem fala detectavel; confira microfone/permissao e tente novamente.",
                )
        else:
            session.audio_validation = None

        if session.transcription:
            transcript_text = session.transcription
            transcript_provider = session.asr_provider_used or asr_provider
            transcript_is_demo = session.is_demo or session.mode == "demo"
            if session.mode == "real" and transcript_is_demo:
                raise ValueError("Modo real recebeu transcricao simulada")
            journey.save_step(
                session,
                "transcription",
                status="completed",
                provider=transcript_provider,
                is_demo=transcript_is_demo,
            )
            session_repo.save(session)
        else:
            started = journey.now_marker()
            journey.save_step(session, "transcription", status="running", provider=asr_provider)
            session_repo.save(session)
            transcript = transcription.transcribe_audio_result(wav, provider=asr_provider)
            _raise_if_cancelled(db, session)
            session.transcription = transcript.text
            session.asr_provider_used = transcript.provider
            transcript_text = transcript.text
            transcript_provider = transcript.provider
            transcript_is_demo = transcript.is_demo
            session.is_demo = session.mode == "demo" or transcript.is_demo
            session.analysis_origin = "demo" if session.is_demo else "real"
            journey.save_step(
                session,
                "transcription",
                status="completed",
                started_at=started,
                provider=transcript.provider,
                is_demo=transcript.is_demo,
            )
            session_repo.save(session)
            if session.mode == "real" and transcript.is_demo:
                raise ValueError("Modo real recebeu transcricao simulada")
        if real_transcription and not transcript_text.strip():
            _reject_analysis(
                session_repo,
                session,
                "empty_transcription",
                "Transcricao vazia; confira a captura e tente novamente.",
            )
        started = journey.now_marker()
        journey.save_step(session, "topics", status="running", provider=topic_provider)
        session_repo.save(session)
        try:
            topic_result = topic_extraction.extract_topics_result(
                transcript_text, provider=topic_provider
            )
        except Exception:
            session.topic_provider_used = topic_provider
            journey.save_step(
                session,
                "topics",
                status="error",
                provider=topic_provider,
                error_code="analysis_failed",
            )
            session_repo.save(session)
            raise
        _raise_if_cancelled(db, session)
        topics = topic_result.topics
        session.topic_provider_used = topic_result.provider
        if session.mode == "real" and topic_result.is_demo:
            raise ValueError("Modo real recebeu topicos simulados")
        journey.save_step(
            session,
            "topics",
            status="completed",
            started_at=started,
            provider=topic_result.provider,
            is_demo=topic_result.is_demo,
        )
        session_repo.save(session)

        started = journey.now_marker()
        journey.save_step(session, "result", status="running")
        session_repo.save(session)
        words = clarity_evaluation.word_count(transcript_text)
        diversity = clarity_evaluation.lexical_diversity(transcript_text)
        coverage = clarity_evaluation.topic_coverage(len(topics))
        clarity = clarity_evaluation.clarity_score(transcript_text, duration, len(topics))
        _raise_if_cancelled(db, session)

        topic_repo.replace_many(session.id, topics)
        metric_repo.replace_many(
            session.id,
            {
                "duration_seconds": (round(duration, 2), "s"),
                "word_count": (float(words), "words"),
                "topic_count": (float(len(topics)), "count"),
                "lexical_diversity": (diversity, "ratio"),
                "topic_coverage": (coverage, "ratio"),
                "clarity_score": (clarity, "score_0_10"),
            },
        )

        now = datetime.now(UTC)
        session.ended_at = now
        _raise_if_deleting(db, session)
        session.duration_seconds = duration
        session.transcription = transcript_text
        session.clarity_score = clarity
        session.status = SessionStatus.completed
        session.asr_provider_used = transcript_provider
        session.topic_provider_used = topic_result.provider
        session.metric_method_version = "heuristic-v1"
        session.is_demo = session.mode == "demo" or transcript_is_demo or topic_result.is_demo
        session.analysis_origin = "demo" if session.is_demo else "real"
        journey.save_step(
            session,
            "result",
            status="completed",
            started_at=started,
            provider="heuristic-v1",
            is_demo=session.is_demo,
        )
        saved = session_repo.save(session)
        from app.services import session_lifecycle

        try:
            session_lifecycle.remove_raw_audio_after_success(db, saved)
        except (session_lifecycle.LifecycleRejectedError, OSError):
            # The valid result is already committed. Cleanup must never turn it
            # into a failed analysis or trigger transcription/extraction again.
            saved.error_code = "audio_cleanup_failed"
            saved.error_message = (
                "Resultado salvo; exclusao do audio pendente. Tente limpar novamente."
            )
            session_repo.save(saved)
        return saved
    except Exception:
        if isinstance(session.status, SessionStatus) and session.status == SessionStatus.error:
            raise
        db.rollback()
        session = db.get(StudySession, session.id) or session
        if session.status == SessionStatus.cancelled:
            return session
        if session.deletion_pending:
            raise
        _mark_running_step_error(session)
        session.status = SessionStatus.error
        session.ended_at = datetime.now(UTC)
        session.error_code = session.error_code or "analysis_failed"
        session.error_message = session.error_message or "Falha durante a analise da sessao."
        session_repo.save(session)
        raise


def _reject_analysis(
    session_repo: SessionRepository,
    session: StudySession,
    code: str,
    message: str,
) -> None:
    session.status = SessionStatus.error
    session.ended_at = datetime.now(UTC)
    session.clarity_score = None
    session.error_code = code
    session.error_message = message
    session_repo.save(session)
    raise AnalysisRejectedError(message)


def _mark_running_step_error(session: StudySession) -> None:
    state = journey.load_journey(session)
    for step in ("result", "topics", "transcription", "capture"):
        if state.get(step, {}).get("status") == "running":
            journey.save_step(session, step, status="error", error_code="analysis_failed")
            return


def _raise_if_deleting(db: Session, session: StudySession) -> None:
    db.refresh(session)
    if session.deletion_pending:
        db.rollback()
        raise AnalysisRejectedError("Sessao marcada para exclusao")


def _raise_if_cancelled(db: Session, session: StudySession) -> None:
    db.refresh(session)
    if session.status == SessionStatus.cancelled:
        db.rollback()
        raise AnalysisRejectedError("Sessao cancelada")

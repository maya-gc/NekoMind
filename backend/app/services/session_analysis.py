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
) -> StudySession:
    """Executa o pipeline completo e atualiza a sessao no banco."""
    session_repo = SessionRepository(db)
    claimed = session_repo.claim_processing(session.id, finish_request_id)
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
        wav = audio_processing.merge_session_audio(db, session.id)
        duration = audio_processing.estimate_duration_seconds(db, session.id)

        real_transcription = session.mode == "real" or asr_provider != "mock"
        if real_transcription:
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

        transcript = transcription.transcribe_audio_result(wav, provider=asr_provider)
        session.asr_provider_used = transcript.provider
        session_repo.save(session)
        if session.mode == "real" and transcript.is_demo:
            raise ValueError("Modo real recebeu transcricao simulada")
        if real_transcription and not transcript.text.strip():
            _reject_analysis(
                session_repo,
                session,
                "empty_transcription",
                "Transcricao vazia; confira a captura e tente novamente.",
            )
        topic_result = topic_extraction.extract_topics_result(
            transcript.text, provider=topic_provider
        )
        topics = topic_result.topics
        if session.mode == "real" and topic_result.is_demo:
            raise ValueError("Modo real recebeu topicos simulados")

        words = clarity_evaluation.word_count(transcript.text)
        diversity = clarity_evaluation.lexical_diversity(transcript.text)
        coverage = clarity_evaluation.topic_coverage(len(topics))
        clarity = clarity_evaluation.clarity_score(transcript.text, duration, len(topics))

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
        session.duration_seconds = duration
        session.transcription = transcript.text
        session.clarity_score = clarity
        session.status = SessionStatus.completed
        session.asr_provider_used = transcript.provider
        session.topic_provider_used = topic_result.provider
        session.is_demo = session.mode == "demo" or transcript.is_demo or topic_result.is_demo
        session.analysis_origin = "demo" if session.is_demo else "real"
        return session_repo.save(session)
    except Exception:
        if isinstance(session.status, SessionStatus) and session.status == SessionStatus.error:
            raise
        db.rollback()
        session = db.get(StudySession, session.id) or session
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

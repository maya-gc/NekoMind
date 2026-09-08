"""Orquestracao da analise de uma sessao ao ser finalizada.

Pipeline: junta o audio -> transcreve (ASR) -> extrai topicos (LLM) ->
calcula metricas heuristicas -> persiste tudo e fecha a sessao.
"""
from __future__ import annotations

from datetime import datetime, timezone

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


def analyze_session(db: Session, session: StudySession) -> StudySession:
    """Executa o pipeline completo e atualiza a sessao no banco."""
    settings = get_settings()
    session_repo = SessionRepository(db)
    topic_repo = TopicRepository(db)
    metric_repo = MetricRepository(db)

    session.status = SessionStatus.processing
    session_repo.save(session)

    try:
        wav = audio_processing.merge_session_audio(db, session.id)
        duration = audio_processing.estimate_duration_seconds(db, session.id)

        text = transcription.transcribe_audio(wav)
        topics = topic_extraction.extract_topics(text)

        words = clarity_evaluation.word_count(text)
        diversity = clarity_evaluation.lexical_diversity(text)
        coverage = clarity_evaluation.topic_coverage(len(topics))
        clarity = clarity_evaluation.clarity_score(text, duration, len(topics))

        topic_repo.create_many(session.id, topics)
        metric_repo.create_many(
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

        now = datetime.now(timezone.utc)
        session.ended_at = now
        session.duration_seconds = duration
        session.transcription = text
        session.clarity_score = clarity
        session.status = SessionStatus.completed
        # Marca como demonstracao quando adapters de IA estao em mock.
        session.is_demo = (
            settings.asr_provider == "mock" or settings.llm_provider == "mock"
        )
        return session_repo.save(session)
    except Exception:
        session.status = SessionStatus.error
        session.ended_at = datetime.now(timezone.utc)
        session_repo.save(session)
        raise

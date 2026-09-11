"""Conexao e sessao do banco de dados.

SQLite e o banco validado do MVP. Outros bancos exigem migracao e testes proprios.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.database.migrations import (
    SESSION_MIGRATION_VERSION,
    STUDY_SESSION_ADDITIVE_COLUMNS,
)
from app.database.models import Base


def _make_engine():
    settings = get_settings()
    url = settings.database_url
    connect_args = {}
    if url.startswith("sqlite"):
        # Necessario para uso do SQLite pelo FastAPI em threads diferentes.
        connect_args["check_same_thread"] = False
    return create_engine(url, connect_args=connect_args)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Cria as tabelas (MVP sem Alembic; ver database/migrations/)."""
    migrate_sqlite_schema(engine)
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_indexes(engine)
    mark_interrupted_sessions_failed(engine)


def migrate_sqlite_schema(target_engine: Engine = engine) -> None:
    """Additive compatibility migrations for existing MVP SQLite databases."""
    if not str(target_engine.url).startswith("sqlite"):
        return
    inspector = inspect(target_engine)
    if "study_sessions" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("study_sessions")}
    additions = STUDY_SESSION_ADDITIVE_COLUMNS
    missing = [name for name in additions if name not in columns]
    if missing:
        _backup_sqlite_file(target_engine)
    with target_engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version VARCHAR(120) PRIMARY KEY, applied_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
            )
        )
        for name, sql_type in additions.items():
            if name not in columns:
                conn.execute(text(f"ALTER TABLE study_sessions ADD COLUMN {name} {sql_type}"))
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_study_sessions_start_request_id "
                "ON study_sessions(start_request_id) WHERE start_request_id IS NOT NULL"
            )
        )
        conn.execute(
            text("INSERT OR IGNORE INTO schema_migrations (version) VALUES (:version)"),
            {"version": SESSION_MIGRATION_VERSION},
        )


def ensure_sqlite_indexes(target_engine: Engine = engine) -> None:
    if not str(target_engine.url).startswith("sqlite"):
        return
    inspector = inspect(target_engine)
    if "study_sessions" not in inspector.get_table_names():
        return
    with target_engine.begin() as conn:
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_study_sessions_start_request_id "
                "ON study_sessions(start_request_id) WHERE start_request_id IS NOT NULL"
            )
        )
        if "audio_chunks" in inspector.get_table_names():
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_audio_chunks_session_sequence "
                    "ON audio_chunks(session_id, sequence)"
                )
            )


def mark_interrupted_sessions_failed(target_engine: Engine = engine) -> None:
    if not str(target_engine.url).startswith("sqlite"):
        return
    inspector = inspect(target_engine)
    if "study_sessions" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("study_sessions")}
    if not {"status", "error_code", "error_message"}.issubset(columns):
        return
    with target_engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE study_sessions "
                "SET status='recovery', error_code='backend_restarted', "
                "error_message='Sessao interrompida pelo reinicio do backend.' "
                "WHERE status IN ('recording', 'paused', 'processing')"
            )
        )


def _backup_sqlite_file(target_engine: Engine) -> None:
    database = target_engine.url.database
    if not database or database == ":memory:":
        return
    source = Path(database)
    if not source.exists():
        return
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    backup = source.with_name(f"{source.name}.bak-{stamp}")
    # A file copy cannot guarantee a consistent snapshot with WAL. Fail closed.
    with sqlite3.connect(source) as src, sqlite3.connect(backup) as dst:
        src.backup(dst)


def get_db() -> Iterator[Session]:
    """Dependency do FastAPI: fornece uma Session por requisicao."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager para uso fora de rotas (ex.: WebSocket)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

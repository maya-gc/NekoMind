"""SQLite additive migration tests for legacy databases."""

from __future__ import annotations

import sqlite3

from sqlalchemy import create_engine, inspect, text

from app.database.connection import init_db, migrate_sqlite_schema
from app.database.models import Base


def test_migrate_sqlite_schema_adds_mvp_columns_to_existing_database(tmp_path) -> None:
    db_path = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE study_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title VARCHAR(200),
                    started_at DATETIME,
                    ended_at DATETIME,
                    duration_seconds FLOAT,
                    status VARCHAR(10),
                    transcription TEXT,
                    clarity_score FLOAT,
                    is_demo BOOLEAN
                )
                """
            )
        )
        conn.execute(
            text(
                "INSERT INTO study_sessions "
                "(title, started_at, duration_seconds, status, is_demo) "
                "VALUES ('Legado', '2026-09-10 00:00:00', 0.0, 'recording', 0)"
            )
        )

    migrate_sqlite_schema(engine)
    Base.metadata.create_all(bind=engine)

    columns = {column["name"] for column in inspect(engine).get_columns("study_sessions")}
    assert {
        "start_request_id",
        "finish_request_id",
        "mode",
        "asr_provider_used",
        "topic_provider_used",
        "error_code",
        "error_message",
        "audio_validation",
        "subject",
        "subject_confirmed",
        "metric_method_version",
        "journey_json",
        "deletion_pending",
    } <= columns

    with engine.connect() as conn:
        preserved = conn.execute(text("SELECT title, status FROM study_sessions")).first()
    assert preserved == ("Legado", "recording")


def test_migrate_sqlite_schema_creates_valid_backup_when_database_uses_wal(tmp_path) -> None:
    db_path = tmp_path / "legacy_wal.db"
    raw = sqlite3.connect(db_path)
    raw.execute("PRAGMA journal_mode=WAL")
    raw.execute(
        """
        CREATE TABLE study_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title VARCHAR(200),
            status VARCHAR(10),
            is_demo BOOLEAN
        )
        """
    )
    raw.execute(
        "INSERT INTO study_sessions (title, status, is_demo) VALUES ('Wal', 'recording', 0)"
    )
    raw.commit()
    raw.close()

    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    migrate_sqlite_schema(engine)

    backups = list(tmp_path.glob("legacy_wal.db.bak-*"))
    assert len(backups) == 1
    backup = sqlite3.connect(backups[0])
    try:
        row = backup.execute("SELECT title, status FROM study_sessions").fetchone()
    finally:
        backup.close()
    assert row == ("Wal", "recording")


def test_init_marks_interrupted_sessions_for_recovery(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "recovery.db"
    monkeypatch.setenv("NEKOMIND_DATABASE_URL", f"sqlite:///{db_path}")

    from sqlalchemy.orm import sessionmaker

    from app.config import get_settings
    from app.database import connection
    from app.database.models import SessionStatus, StudySession

    get_settings.cache_clear()
    monkeypatch.setattr(connection, "engine", connection._make_engine())
    monkeypatch.setattr(
        connection,
        "SessionLocal",
        sessionmaker(bind=connection.engine, autoflush=False, expire_on_commit=False),
    )
    connection.init_db()
    with connection.SessionLocal() as db:
        db.add(StudySession(title="Interrompida", status=SessionStatus.recording))
        db.commit()

    connection.init_db()

    with connection.SessionLocal() as db:
        session = db.query(StudySession).one()
    assert session.status == SessionStatus.recovery
    assert session.error_code == "backend_restarted"


def test_fresh_database_init_has_request_id_unique_index(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "fresh.db"
    monkeypatch.setenv("NEKOMIND_DATABASE_URL", f"sqlite:///{db_path}")

    from sqlalchemy.orm import sessionmaker

    from app.config import get_settings
    from app.database import connection

    get_settings.cache_clear()
    monkeypatch.setattr(connection, "engine", connection._make_engine())
    monkeypatch.setattr(
        connection,
        "SessionLocal",
        sessionmaker(bind=connection.engine, autoflush=False, expire_on_commit=False),
    )
    init_db()

    with connection.engine.connect() as conn:
        indexes = conn.execute(text("PRAGMA index_list('study_sessions')")).fetchall()
    index_names = {row[1] for row in indexes}
    assert "ix_study_sessions_start_request_id" in index_names


def test_backup_failure_blocks_migration(tmp_path, monkeypatch):
    import pytest

    from app.database import connection

    db_path = tmp_path / "backup_error.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE study_sessions(id INTEGER PRIMARY KEY)"))

    def broken_backup(*args, **kwargs):
        raise sqlite3.OperationalError("backup failed")

    monkeypatch.setattr(connection.sqlite3, "connect", broken_backup)
    with pytest.raises(sqlite3.OperationalError):
        migrate_sqlite_schema(engine)
    assert {c["name"] for c in inspect(engine).get_columns("study_sessions")} == {"id"}


def test_deleted_largest_session_id_is_not_reused_by_repository(client) -> None:
    from app.database.connection import SessionLocal
    from app.repositories.session_repository import SessionRepository

    with SessionLocal() as db:
        repo = SessionRepository(db)
        first = repo.create(title="Primeira", request_id="start-delete-id")
        first_id = first.id
        db.delete(first)
        db.commit()

    with SessionLocal() as db:
        second = SessionRepository(db).create(title="Segunda", request_id="start-after-delete")

    assert second.id > first_id


def test_deleted_start_request_id_is_tombstoned_without_private_content(client) -> None:
    import pytest

    from app.database.connection import SessionLocal
    from app.database.models import DeletedSessionTombstone
    from app.repositories.session_repository import (
        SessionRepository,
        TombstonedSessionRequestError,
    )

    with SessionLocal() as db:
        repo = SessionRepository(db)
        session = repo.create(
            title="Privado",
            request_id="start-deleted-replay",
            capture_source="mac",
            device_session_id="device-private",
        )
        sid = session.id
        db.delete(session)
        db.commit()

    with SessionLocal() as db:
        tombstone = db.get(DeletedSessionTombstone, sid)
        assert tombstone is not None
        assert tombstone.start_request_id == "start-deleted-replay"
        assert not hasattr(tombstone, "title")
        assert not hasattr(tombstone, "transcription")
        with pytest.raises(TombstonedSessionRequestError):
            SessionRepository(db).create(
                title="Replay",
                request_id="start-deleted-replay",
                capture_source="mac",
                device_session_id="device-private",
            )


def test_migration_adds_delete_tombstone_trigger_to_legacy_sqlite(tmp_path) -> None:
    db_path = tmp_path / "legacy_tombstone.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE study_sessions (
                    id INTEGER PRIMARY KEY,
                    title VARCHAR(200),
                    status VARCHAR(10),
                    is_demo BOOLEAN,
                    start_request_id VARCHAR(100)
                )
                """
            )
        )
        conn.execute(
            text(
                "INSERT INTO study_sessions (id, title, status, is_demo, start_request_id) "
                "VALUES (7, 'Legado privado', 'completed', 0, 'legacy-start')"
            )
        )

    migrate_sqlite_schema(engine)
    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM study_sessions WHERE id=7"))
        tombstone = conn.execute(
            text(
                "SELECT session_id, start_request_id FROM deleted_session_tombstones "
                "WHERE session_id=7"
            )
        ).first()
        columns = {
            row[1] for row in conn.execute(text("PRAGMA table_info('deleted_session_tombstones')"))
        }

    assert tombstone == (7, "legacy-start")
    assert "title" not in columns
    assert "transcription" not in columns

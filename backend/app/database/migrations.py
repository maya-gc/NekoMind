"""Versioned additive SQLite migrations for the touch + Mac MVP."""

from __future__ import annotations

SESSION_MIGRATION_VERSION = "20260911_nm019_backend_lifecycle"
SESSION_TOMBSTONE_MIGRATION_VERSION = "20260911_session_delete_tombstones"

STUDY_SESSION_ADDITIVE_COLUMNS = {
    "request_id": "VARCHAR(100)",
    "start_request_id": "VARCHAR(100)",
    "finish_request_id": "VARCHAR(100)",
    "device_session_id": "VARCHAR(100)",
    "capture_source": "VARCHAR(80)",
    "asr_provider_config": "VARCHAR(80)",
    "topic_provider_config": "VARCHAR(80)",
    "asr_provider_used": "VARCHAR(80)",
    "topic_provider_used": "VARCHAR(80)",
    "analysis_origin": "VARCHAR(80)",
    "speech_validation": "TEXT",
    "audio_validation": "TEXT",
    "error_code": "VARCHAR(80)",
    "error_message": "TEXT",
    "mode": "VARCHAR(16) DEFAULT 'demo' NOT NULL",
    "subject": "VARCHAR(200)",
    "subject_confirmed": "BOOLEAN DEFAULT 0 NOT NULL",
    "metric_method_version": "VARCHAR(40) DEFAULT 'heuristic-v1' NOT NULL",
    "journey_json": "TEXT DEFAULT '{}' NOT NULL",
    "deletion_pending": "BOOLEAN DEFAULT 0 NOT NULL",
}

DELETED_SESSION_TOMBSTONE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS deleted_session_tombstones (
    session_id INTEGER PRIMARY KEY,
    start_request_id VARCHAR(100) UNIQUE,
    deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""

DELETED_SESSION_TOMBSTONE_TRIGGER_SQL = """
CREATE TRIGGER IF NOT EXISTS trg_study_sessions_delete_tombstone
AFTER DELETE ON study_sessions
BEGIN
    INSERT OR IGNORE INTO deleted_session_tombstones (session_id, start_request_id)
    VALUES (OLD.id, OLD.start_request_id);
END
"""

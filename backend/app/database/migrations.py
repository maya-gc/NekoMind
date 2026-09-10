"""Versioned additive SQLite migrations for the touch + Mac MVP."""

from __future__ import annotations

SESSION_MIGRATION_VERSION = "20260910_touch_mac_mvp_backend"

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
}

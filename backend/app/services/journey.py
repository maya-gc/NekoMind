"""Persistent analysis journey helpers."""

from __future__ import annotations

import json
from time import monotonic
from typing import Any

from app.database.models import StudySession

DEFAULT_STEPS = ("capture", "transcription", "topics", "result")


def empty_journey() -> dict[str, dict[str, Any]]:
    return {
        step: {
            "status": "waiting",
            "duration_ms": 0,
            "provider": None,
            "is_demo": False,
        }
        for step in DEFAULT_STEPS
    }


def load_journey(session: StudySession) -> dict[str, dict[str, Any]]:
    try:
        parsed = json.loads(session.journey_json or "{}")
    except json.JSONDecodeError:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    journey = empty_journey()
    for step, value in parsed.items():
        if isinstance(value, dict):
            journey[step] = {**journey.get(step, {}), **value}
    return journey


def save_step(
    session: StudySession,
    step: str,
    *,
    status: str,
    started_at: float | None = None,
    duration_ms: int | None = None,
    provider: str | None = None,
    is_demo: bool | None = None,
    error_code: str | None = None,
) -> None:
    current = load_journey(session)
    entry = current.get(step, {})
    entry["status"] = status
    if duration_ms is not None:
        entry["duration_ms"] = max(0, int(duration_ms))
    elif started_at is not None:
        entry["duration_ms"] = max(0, int((monotonic() - started_at) * 1000))
    elif status == "running":
        entry["_started_at"] = monotonic()
        entry.setdefault("duration_ms", 0)
    elif "_started_at" in entry:
        entry["duration_ms"] = max(0, int((monotonic() - float(entry["_started_at"])) * 1000))
    else:
        entry.setdefault("duration_ms", 0)
    if provider is not None:
        entry["provider"] = provider
    else:
        entry.setdefault("provider", None)
    if is_demo is not None:
        entry["is_demo"] = bool(is_demo)
    else:
        entry.setdefault("is_demo", False)
    if error_code:
        entry["error_code"] = error_code
    elif "error_code" in entry and status != "error":
        entry.pop("error_code", None)
    if status != "running":
        entry.pop("_started_at", None)
    current[step] = entry
    session.journey_json = json.dumps(current, ensure_ascii=False, sort_keys=True)


def now_marker() -> float:
    return monotonic()

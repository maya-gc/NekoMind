"""Strict, bounded JSON Lines protocol shared by Mac transports."""

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

MAX_LINE = 4096


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    v: Literal[1]
    type: Literal["command"]
    request_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
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
        "hint",
        "answer",
    ]
    session_id: int | None = Field(default=None, gt=0, le=2147483647)
    mission_index: StrictInt | None = Field(default=None, ge=0, le=29)

    @field_validator("v", mode="before")
    @classmethod
    def strict_version(cls, value):
        if type(value) is not int:
            raise ValueError("version must be an integer")
        return value

    @model_validator(mode="after")
    def mission_belongs_to_start(self):
        if self.mission_index is not None and self.command != "start":
            raise ValueError("mission_index is only valid for start")
        return self


def _unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate_key")
        value[key] = item
    return value


def decode_line(raw: bytes) -> dict:
    if len(raw) > MAX_LINE or not raw.endswith(b"\n"):
        raise ValueError("invalid_frame")
    data = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=_unique_pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("invalid_number")),
    )
    command = Command.model_validate(data).model_dump()
    if command["mission_index"] is None:
        del command["mission_index"]
    return command


def decode_display_ack(raw: bytes) -> dict:
    """Read a bounded, content-free receipt from the physical LCD renderer."""
    if len(raw) > MAX_LINE or not raw.endswith(b"\n"):
        raise ValueError("invalid_frame")
    try:
        message = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("invalid_number")),
        )
    except (UnicodeError, ValueError) as exc:
        raise ValueError("invalid_display_ack") from exc
    if (
        type(message) is not dict
        or set(message) != {"v", "type", "state", "mission_count", "mission_index", "draw_ok"}
        or type(message["v"]) is not int
        or message["v"] != 1
        or message["type"] != "display_ack"
        or type(message["state"]) is not str
        or message["state"]
        not in {"IDLE", "PENDING", "CHECKING", "READY", "RECOVERY", "RECORDING",
                "PAUSED", "PROCESSING", "SUCCESS", "ERROR"}
        or type(message["mission_count"]) is not int
        or not 0 <= message["mission_count"] <= 30
        or type(message["mission_index"]) is not int
        or not 0 <= message["mission_index"] < max(1, message["mission_count"])
        or type(message["draw_ok"]) is not bool
    ):
        raise ValueError("invalid_display_ack")
    return message


def encode_line(message: dict) -> bytes:
    raw = (
        json.dumps(message, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n"
    ).encode()
    if len(raw) > MAX_LINE:
        raise ValueError("result_too_large")
    return raw


def validate_result(row: dict, session_id: int) -> None:
    if not isinstance(row, dict) or type(row.get("id")) is not int or row["id"] != session_id:
        raise ValueError("wrong_session")
    if (
        row.get("status") != "completed"
        or type(row.get("is_demo")) is not bool
        or row.get("deletion_pending") is True
    ):
        raise ValueError("invalid_result")
    for name in ("asr_provider", "topic_provider", "transcription"):
        if not isinstance(row.get(name), str) or not row[name].strip():
            raise ValueError("invalid_origin_or_text")
    if not row["is_demo"] and (row["asr_provider"] == "mock" or row["topic_provider"] == "mock"):
        raise ValueError("invalid_origin")
    topics = row.get("topics")
    if not isinstance(topics, list) or len(topics) > 100:
        raise ValueError("invalid_topics")
    for topic in topics:
        if (
            not isinstance(topic, dict)
            or type(topic.get("session_id")) is not int
            or topic.get("session_id") != session_id
            or not isinstance(topic.get("name"), str)
            or not topic["name"].strip()
        ):
            raise ValueError("invalid_topic")
    report = row.get("content_report")
    if report is not None and (
        not isinstance(report, dict)
        or report.get("content_id") != row.get("reference_content_id")
        or report.get("content_version") != row.get("reference_version")
        or report.get("origin") != ("demo" if row["is_demo"] else "real")
        or not isinstance(report.get("points"), list)
    ):
        raise ValueError("invalid_content_report")

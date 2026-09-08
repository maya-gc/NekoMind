"""WebSocket /ws/device - canal com o dispositivo ESP32-S3.

Aceita mensagens do protocolo JSON Lines (docs/iot_protocol.md) ja em
JSON nativo. Responde com mensagens de confirmacao ou erro:
  {"type": "ack", ...} / {"type": "error", ...}
"""
from __future__ import annotations

import base64
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.database.connection import session_scope
from app.repositories.session_repository import SessionRepository
from app.services import audio_ingestion, session_analysis

logger = logging.getLogger(__name__)

router = APIRouter()


async def _handle_message(ws: WebSocket, msg: dict) -> None:
    mtype = msg.get("type")

    if mtype == "session_start":
        with session_scope() as db:
            session = SessionRepository(db).create(title=msg.get("title"))
            await ws.send_json(
                {"type": "ack", "for": "session_start", "session_id": session.id}
            )

    elif mtype == "audio_chunk":
        session_id = int(msg.get("session_id", 0))
        seq = int(msg.get("seq", 0))
        raw = base64.b64decode(msg.get("data", "")) if msg.get("data") else b""
        with session_scope() as db:
            session = SessionRepository(db).get(session_id)
            if session is None:
                await ws.send_json(
                    {"type": "error", "detail": "sessao desconhecida"}
                )
                return
            if raw:
                audio_ingestion.save_chunk(db, session, raw, seq)
            await ws.send_json({"type": "ack", "for": "audio_chunk", "seq": seq})

    elif mtype == "session_end":
        session_id = int(msg.get("session_id", 0))
        with session_scope() as db:
            session = SessionRepository(db).get(session_id)
            if session is None:
                await ws.send_json(
                    {"type": "error", "detail": "sessao desconhecida"}
                )
                return
            session = session_analysis.analyze_session(db, session)
            await ws.send_json(
                {
                    "type": "analysis_result",
                    "session_id": session.id,
                    "status": session.status.value,
                    "clarity_score": session.clarity_score,
                }
            )

    elif mtype == "device_status":
        await ws.send_json({"type": "ack", "for": "device_status"})

    else:
        await ws.send_json({"type": "error", "detail": f"tipo desconhecido: {mtype}"})


@router.websocket("/ws/device")
async def device_ws(ws: WebSocket) -> None:
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "detail": "JSON invalido"})
                continue
            await _handle_message(ws, msg)
    except WebSocketDisconnect:
        logger.info("dispositivo desconectado do WebSocket")

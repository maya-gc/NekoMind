"""Reject the legacy embedded-audio path; MVP commands use the local Mac bridge."""

from fastapi import APIRouter, WebSocket

router = APIRouter()


@router.websocket("/ws/device")
async def device_ws(ws: WebSocket) -> None:
    await ws.accept()
    await ws.send_json(
        {
            "type": "error",
            "code": "legacy_transport_disabled",
            "detail": "Use o bridge Mac por USB/serial; audio embarcado e um recurso futuro.",
        }
    )
    await ws.close(code=1008)

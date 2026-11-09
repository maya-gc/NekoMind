"""Virtual LCD touch: sends the same JSON Lines the ESP32-S3 firmware sends.

Every message goes through the real wire codec (``decode_line`` /
``encode_line``) exactly like ``run_serial`` does, so protocol violations fail
here too. Instead of a person tapping the display, a scenario calls ``tap``
with the command a button would produce (Começar, Finalizar, Pedir dica,
Responder...).
"""

from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass, field

from app.mac.protocol import decode_line, encode_line

# Button label on the LCD -> protocol command (see docs/interactive-dialogue.md).
BUTTONS = {
    "Diagnóstico": "diagnose",
    "Começar": "start",
    "Pausar": "pause",
    "Continuar": "resume",
    "Finalizar": "finish",
    "Pedir dica": "hint",
    "Responder": "answer",
    "Tentar de novo": "retry",
    "Voltar": "reset",
    "Retomar": "recover",
    "Descartar": "discard",
}


@dataclass
class VirtualTouch:
    bridge: object
    nonce: str = field(default_factory=lambda: "vt" + secrets.token_hex(6))
    counter: int = 0
    wire: list = field(default_factory=list)

    def _frame(self, command: str, session_id=None, mission_index=None) -> bytes:
        self.counter += 1
        message = {
            "v": 1,
            "type": "command",
            "request_id": f"{self.nonce}-{self.counter}",
            "command": command,
            "session_id": session_id,
        }
        if mission_index is not None:
            message["mission_index"] = mission_index
        return (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")

    def send(self, command: str, session_id=None, mission_index=None) -> dict:
        frame = self._frame(command, session_id, mission_index)
        decoded = decode_line(frame)  # same validation as the serial loop
        marker = getattr(self.bridge, "mark_serial_connected", None)
        if marker is not None:  # run_serial does this for every valid frame
            marker()
        response = self.bridge.handle(decoded)
        raw = encode_line(response)
        reply = json.loads(raw.decode("utf-8"))
        self.wire.append({"tx": frame.decode().strip(), "rx": raw.decode().strip()})
        self.pump()
        return reply

    def tap(self, button: str, session_id=None, mission_index=None) -> dict:
        """Simulate a tap on an LCD button by its label."""
        return self.send(BUTTONS[button], session_id, mission_index)

    def close(self):
        marker = getattr(self.bridge, "mark_serial_disconnected", None)
        if marker is not None:
            marker()

    def pump(self):
        tick = getattr(self.bridge, "tick", None)
        if tick is not None:
            tick()
        for event in self.bridge.drain_events():
            self.wire.append({"event": json.dumps(event, ensure_ascii=False)})

    def poll(self, session_id, until, *, timeout=60.0, interval=0.3) -> dict:
        """Heartbeat ``status`` like the firmware until ``until(reply)`` is true."""
        deadline = time.monotonic() + timeout
        reply = {}
        while time.monotonic() < deadline:
            reply = self.send("status", session_id)
            if until(reply):
                return reply
            time.sleep(interval)
        raise TimeoutError(f"Tempo esgotado aguardando estado; ultimo: {reply.get('state')}")

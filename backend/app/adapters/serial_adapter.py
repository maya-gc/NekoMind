"""Adaptador da serial USB (JSON Lines) com o dispositivo ESP32-S3.

Stub para uso futuro em integracao continua com o firmware. Le linhas
JSON do protocolo definido em docs/iot_protocol.md. Nao e usado pelos
endpoints HTTP no MVP - o envio de audio ao backend ocorre via
POST /api/v1/sessions/{id}/audio ou pelo WebSocket /ws/device.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterator

logger = logging.getLogger(__name__)


class SerialAdapter:
    """Leitor de JSON Lines de uma porta serial (stub).

    Para ativar, defina NEKOMIND_SERIAL_PORT (ex.: COM5) e instale
    `pyserial`. A implementacao abaixo so e carregada sob demanda.
    """

    def __init__(self, port: str, baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate

    def open(self):
        try:
            import serial  # type: ignore  # pyserial e opcional no MVP
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "pyserial nao instalado; instale para usar a serial"
            ) from exc
        return serial.Serial(self.port, self.baudrate, timeout=1)

    def iter_messages(self) -> Iterator[dict]:
        with self.open() as ser:
            for raw in ser:
                try:
                    yield json.loads(raw.decode("utf-8", errors="replace"))
                except json.JSONDecodeError:
                    logger.warning("linha serial invalida ignorada: %r", raw[:80])

    def send_json(self, ser, message: dict) -> None:
        ser.write((json.dumps(message) + "\n").encode("utf-8"))


def make_serial_handler(on_message: Callable[[dict], None]) -> None:
    """Ponto de extensao: loop em thread para alimentar o pipeline."""
    raise NotImplementedError("integracao serial continua - fora do MVP")

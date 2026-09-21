"""Bounded serial framing; no audio or console log payloads on the wire."""

import logging
import os
from time import monotonic

from app.mac.protocol import MAX_LINE, decode_line, encode_line

logger = logging.getLogger(__name__)


def run_serial(port, bridge, stop, *, heartbeat_timeout=8.0):
    trace = os.environ.get("NEKOMIND_SERIAL_TRACE") == "1"
    pending = bytearray()
    dropping = False
    last_seen = monotonic()
    disconnected = False
    try:
        while not stop.is_set():
            raw = port.read(256)
            for byte in raw:
                if dropping:
                    if byte == 10:
                        dropping = False
                    continue
                pending.append(byte)
                if len(pending) > MAX_LINE:
                    pending.clear()
                    dropping = byte != 10
                    continue
                if byte != 10:
                    continue
                frame = bytes(pending)
                pending.clear()
                try:
                    message = decode_line(frame)
                except ValueError:
                    if trace:
                        logger.info("Serial descartou quadro invalido (%d bytes).", len(frame))
                    continue  # Invalid traffic is not a heartbeat or acknowledgement.
                last_seen = monotonic()
                disconnected = False
                if trace:
                    logger.info("Serial recebeu comando: %s", message.get("command"))
                marker = getattr(bridge, "mark_serial_connected", None)
                if marker is not None:
                    marker()
                handle_started = monotonic()
                response = bridge.handle(message)
                port.write(encode_line(response))
                # Captura/permissao/HTTP podem demorar. A janela de desconexao
                # comeca depois da resposta, nao antes do trabalho bloqueante.
                last_seen = monotonic()
                if trace:
                    logger.info("Serial respondeu %s em %.2fs", message.get("command"),
                                last_seen - handle_started)
            bridge.check_capture()
            tick = getattr(bridge, "tick", None)
            if tick is not None:
                tick()
            for response in bridge.drain_events():
                port.write(encode_line(response))
            if monotonic() - last_seen > heartbeat_timeout and not disconnected:
                if trace:
                    logger.warning("Serial sem comando valido por %.2fs", monotonic() - last_seen)
                marker = getattr(bridge, "mark_serial_disconnected", None)
                if marker is not None:
                    marker()
                bridge.disconnect()
                disconnected = True
    finally:
        marker = getattr(bridge, "mark_serial_disconnected", None)
        if marker is not None:
            marker()
        bridge.disconnect()

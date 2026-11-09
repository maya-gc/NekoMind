"""Hardware smoke test of the ESP32-S3 over USB, without flashing anything.

    python -m app.devtools.esp_probe            # auto-detects the Espressif port
    python -m app.devtools.esp_probe --port COM3 --seconds 15

Listens to the firmware heartbeat (``status`` every ~2.6 s), answers each one
with ``state=idle`` (DEMO) like the bridge would, and counts the
``display_ack`` receipts the LCD renderer sends back (``draw_ok``). Exit code
0 when at least one command arrived and every ack reported a good draw.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

ESPRESSIF_VID = 0x303A
USB_UART_VIDS = {0x10C4, 0x1A86, 0x0403}  # CP210x, CH340, FTDI


def find_port():
    from serial.tools import list_ports

    ports = list(list_ports.comports())
    for p in ports:
        print(f"  {p.device} | VID:PID={p.vid and hex(p.vid)}:{p.pid and hex(p.pid)} | "
              f"{p.description}")
    esp = [p for p in ports if p.vid == ESPRESSIF_VID] or [
        p for p in ports if p.vid in USB_UART_VIDS
    ]
    return esp[0].device if esp else None


def probe(port: str, seconds: float) -> dict:
    import serial

    stats = {"port": port, "commands": 0, "replies": 0, "acks": 0, "draw_fail": 0, "logs": 0,
             "states": []}
    with serial.Serial(port, 115200, timeout=0.5) as s:
        end, buf = time.time() + seconds, b""
        while time.time() < end:
            buf += s.read(512)
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                text = line.decode("utf-8", "replace").strip()
                start = text.find("{")
                if start < 0:
                    if text:
                        stats["logs"] += 1
                    continue
                if start > 0:
                    stats["logs"] += 1
                try:
                    msg = json.loads(text[start:])
                except ValueError:
                    stats["logs"] += 1
                    continue
                if msg.get("type") == "command":
                    stats["commands"] += 1
                    if msg.get("command") == "status":
                        reply = {"v": 1, "type": "state", "request_id": msg.get("request_id"),
                                 "session_id": None, "state": "idle", "is_demo": True}
                        s.write((json.dumps(reply) + "\n").encode())
                        stats["replies"] += 1
                elif msg.get("type") == "display_ack":
                    stats["acks"] += 1
                    stats["states"].append(msg.get("state"))
                    if not msg.get("draw_ok"):
                        stats["draw_fail"] += 1
    stats["states"] = sorted(set(stats["states"]))
    stats["ok"] = stats["commands"] > 0 and stats["draw_fail"] == 0
    return stats


def main(argv=None):
    parser = argparse.ArgumentParser(description="Teste de fumaça da placa ESP32-S3 (USB)")
    parser.add_argument("--port", default=None)
    parser.add_argument("--seconds", type=float, default=15)
    args = parser.parse_args(argv)
    print("Portas seriais:")
    port = args.port or find_port()
    if not port:
        print("RESULTADO: nenhuma placa ESP encontrada.")
        return 1
    try:
        stats = probe(port, args.seconds)
    except Exception as exc:  # noqa: BLE001 - user-facing hardware message
        print(f"RESULTADO: não foi possível abrir {port}: {exc} (feche monitores seriais).")
        return 1
    print(json.dumps(stats, ensure_ascii=False))
    print("RESULTADO:", "PLACA OK" if stats["ok"] else "PLACA COM PROBLEMA")
    return 0 if stats["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

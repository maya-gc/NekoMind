#!/usr/bin/env bash
# test_bancada.sh - Pipeline MANUAL de bancada (macOS): voce toca no display.
# Backend em segundo plano + bridge com microfone real e voz Kokoro audivel.
# Uso: bash scripts/test_bancada.sh /dev/cu.usbmodem1101 [kokoro|kokoro-file|silent|off] [a.wav b.wav]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"; PY="$BACKEND/.venv/bin/python"
PORT="${1:?Informe a porta: python -m serial.tools.list_ports}"; VOICE="${2:-kokoro}"; shift $(( $# >= 2 ? 2 : 1 ))
AUDIO=(); for f in "$@"; do AUDIO+=(--audio-file "$f"); done
(cd "$BACKEND" && "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000) &
SRV=$!; trap 'kill $SRV 2>/dev/null' EXIT; sleep 3
echo "Operador: http://127.0.0.1:8000/presenter  Plateia: http://127.0.0.1:8000/public"
cd "$BACKEND" && "$PY" -m app.mac --port "$PORT" --voice "$VOICE" ${AUDIO[@]+"${AUDIO[@]}"}

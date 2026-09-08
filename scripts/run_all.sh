#!/usr/bin/env bash
# run_all.sh - Inicia backend e frontend em processos separados.
# Exibe URLs e salva logs em logs/ na raiz do repositorio.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

echo ">> Iniciando backend em http://127.0.0.1:8000 ..."
bash "$ROOT/scripts/run_backend.sh" >"$LOG_DIR/backend.log" 2>&1 &
BACK_PID=$!

echo ">> Iniciando frontend em http://127.0.0.1:8501 ..."
bash "$ROOT/scripts/run_frontend.sh" >"$LOG_DIR/frontend.log" 2>&1 &
FRONT_PID=$!

echo
echo "== URLs =="
echo "  Backend:  http://127.0.0.1:8000  (docs: /docs)"
echo "  Frontend: http://127.0.0.1:8501"
echo "  Logs:     $LOG_DIR"
echo
echo "PIDs: backend=$BACK_PID frontend=$FRONT_PID"
echo "Para encerrar: Ctrl+C (no terminal) ou 'kill $BACK_PID $FRONT_PID'"

trap 'kill "$BACK_PID" "$FRONT_PID" 2>/dev/null || true' EXIT INT TERM
wait
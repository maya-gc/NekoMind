#!/usr/bin/env bash
# apresentar.sh - Modo apresentacao (macOS): checklist, backend, bridge e telas.
#   bash scripts/apresentar.sh                 # modo real (microfone, transcricao, voz Kokoro)
#   bash scripts/apresentar.sh --plano-b       # demo identificado: sem microfone nem modelos
#   bash scripts/apresentar.sh --porta /dev/cu.usbmodem1101 --voz silent
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"; PY="$BACKEND/.venv/bin/python"
PORTA=""; VOZ=kokoro; PLANO_B=0; FORCAR=0; MODELO="${NEKOMIND_ASR_MODEL_SIZE:-small}"
while [ $# -gt 0 ]; do
  case "$1" in
    --porta) PORTA="$2"; shift 2 ;;
    --voz) VOZ="$2"; shift 2 ;;
    --plano-b) PLANO_B=1; shift ;;
    --forcar) FORCAR=1; shift ;;
    *) echo "opcao desconhecida: $1" >&2; exit 2 ;;
  esac
done
[ -x "$PY" ] || { echo "Prepare antes: bash scripts/test_auto.sh" >&2; exit 1; }
cd "$BACKEND"
PF=(--voz "$VOZ" --modelo "$MODELO" --json "$BACKEND/storage/preflight.json")
[ -n "$PORTA" ] && PF+=(--porta "$PORTA")
[ "$PLANO_B" = 1 ] && PF+=(--plano-b)
if ! "$PY" -m app.devtools.preflight "${PF[@]}"; then
  [ "$FORCAR" = 1 ] || { echo; echo "Corrija os itens acima, use --plano-b ou --forcar."; exit 1; }
fi
PORTA="${PORTA:-$("$PY" -c 'import json;print(json.load(open("storage/preflight.json"))["porta"] or "")')}"
[ -n "$PORTA" ] || { echo "Placa nao encontrada." >&2; exit 1; }
if [ "$PLANO_B" = 1 ]; then
  export NEKOMIND_MODE=demo NEKOMIND_ASR_PROVIDER=mock NEKOMIND_LLM_PROVIDER=mock
  BRIDGE_EXTRA=(--simulate)
else
  export NEKOMIND_MODE=real NEKOMIND_ASR_PROVIDER=faster_whisper NEKOMIND_LLM_PROVIDER=local_keywords
  export NEKOMIND_ASR_MODEL_SIZE="$MODELO"
  BRIDGE_EXTRA=()
fi
"$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 >"$BACKEND/storage/backend-apresentacao.log" 2>&1 &
SRV=$!; trap 'kill $SRV 2>/dev/null' EXIT
for _ in $(seq 1 30); do curl -sf http://127.0.0.1:8000/health >/dev/null && break; sleep 0.5; done
open "http://127.0.0.1:8000/presenter" 2>/dev/null; open "http://127.0.0.1:8000/public" 2>/dev/null
echo "Operador: http://127.0.0.1:8000/presenter  |  Plateia: http://127.0.0.1:8000/public"
echo "Placa: $PORTA  |  Ctrl+C encerra tudo."
"$PY" -m app.mac --port "$PORTA" --voice "$VOZ" ${BRIDGE_EXTRA[@]+"${BRIDGE_EXTRA[@]}"}

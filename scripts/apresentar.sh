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
# Supervisor: sobe Ollama/backend/bridge, reinicia o que cair, logs em backend/storage/logs
SUP=(-m app.devtools.supervisor --porta "$PORTA" --voz "$VOZ" --modelo-tutor "${NEKOMIND_TUTOR_MODEL:-qwen2.5:7b}" --abrir)
[ "$PLANO_B" = 1 ] && SUP+=(--plano-b)
echo "Operador: http://127.0.0.1:8000/presenter  |  Plateia: http://127.0.0.1:8000/public"
echo "Placa: $PORTA  |  Ctrl+C encerra tudo (backup do banco ao sair)."
"$PY" "${SUP[@]}"

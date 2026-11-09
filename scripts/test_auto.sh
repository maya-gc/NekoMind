#!/usr/bin/env bash
# test_auto.sh - Pipeline AUTOMATICA e silenciosa (macOS; tambem roda em Linux).
# pytest + testes do frontend + pipeline com toque virtual e voz do sistema (say)
# + teste de fumaca da placa ESP pela USB (use --sem-placa para pular).
# Uso: bash scripts/test_auto.sh [--asr whisper] [--sem-placa] [--porta /dev/cu.usbmodem1101]
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
PY="$BACKEND/.venv/bin/python"
ASR=roteiro; PLACA=1; PORTA=()
while [ $# -gt 0 ]; do
  case "$1" in
    --asr) ASR="$2"; shift 2 ;;
    --sem-placa) PLACA=0; shift ;;
    --porta) PORTA=(--port "$2"); shift 2 ;;
    *) echo "opcao desconhecida: $1" >&2; exit 2 ;;
  esac
done
OUT="$BACKEND/storage/pipeline/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"
res() { printf '%-30s %-5s  %s\n' "$1" "$2" "$3" | tee -a "$OUT/00_resumo.txt"; }
if [ ! -x "$PY" ]; then
  echo ">> Criando ambiente Python do backend..."
  "${PYTHON_BIN:-python3}" -m venv "$BACKEND/.venv"
fi
"$PY" -m pip install -q -r "$BACKEND/requirements-test.txt" >"$OUT/01_pip.txt" 2>&1
(cd "$BACKEND" && "$PY" -m pytest -q -rfEs -p no:cacheprovider) >"$OUT/02_pytest.txt" 2>&1 \
  && res "Backend (pytest)" OK "$(tail -1 "$OUT/02_pytest.txt")" \
  || res "Backend (pytest)" FALHA "$(tail -1 "$OUT/02_pytest.txt")"
if command -v node >/dev/null; then
  (cd "$ROOT" && node --test frontend/tests/*.test.mjs) >"$OUT/03_frontend.txt" 2>&1 \
    && res "Frontend (node --test)" OK "" || res "Frontend (node --test)" FALHA "ver 03_frontend.txt"
else res "Frontend (node --test)" FALHA "Node.js nao instalado"; fi
(cd "$BACKEND" && "$PY" -m app.devtools.pipeline --asr "$ASR" --out "$OUT/pipeline") >"$OUT/04_pipeline.txt" 2>&1 \
  && res "Pipeline toque virtual" OK "" || res "Pipeline toque virtual" FALHA "ver 04_pipeline.txt"
if [ "$PLACA" = 1 ]; then
  (cd "$BACKEND" && "$PY" -m app.devtools.esp_probe "${PORTA[@]}") >"$OUT/05_placa.txt" 2>&1 \
    && res "Placa ESP (USB)" OK "" || res "Placa ESP (USB)" FALHA "$(grep RESULTADO "$OUT/05_placa.txt")"
fi
echo; echo "Logs e relatorio: $OUT"

#!/usr/bin/env bash
# baixar_modelo_asr.sh - Instala faster-whisper e baixa o modelo de transcricao (uma vez).
# Uso: bash scripts/baixar_modelo_asr.sh [small]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/backend/.venv/bin/python"; MODEL="${1:-small}"
[ -x "$PY" ] || { echo "Prepare o backend: bash scripts/test_auto.sh" >&2; exit 1; }
"$PY" -m pip install -q -r "$ROOT/backend/requirements-real.txt"
HF_HUB_DISABLE_XET=1 "$PY" -c "from faster_whisper import WhisperModel; WhisperModel('$MODEL', device='cpu', compute_type='int8'); print('Modelo $MODEL pronto (cache local).')"
echo "Teste: bash scripts/test_auto.sh --asr whisper"

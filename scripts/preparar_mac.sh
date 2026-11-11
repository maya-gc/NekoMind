#!/usr/bin/env bash
# preparar_mac.sh - Deixa o Mac pronto para apresentar: Python 3.12, eSpeak NG, voz
# Kokoro, Ollama + modelo do tutor, modelo de transcricao e checklist.
# Uso: bash scripts/preparar_mac.sh [qwen2.5:7b]
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"; VENV="$BACKEND/.venv"; PY="$VENV/bin/python"
MODELO="${1:-qwen2.5:7b}"
passo() { printf '\n== %s\n' "$1"; }
command -v brew >/dev/null || { echo "Instale o Homebrew: https://brew.sh" >&2; exit 1; }

passo "Python 3.12 e eSpeak NG"
brew list python@3.12 >/dev/null 2>&1 || brew install python@3.12
brew list espeak-ng >/dev/null 2>&1 || brew install espeak-ng
PY312="$(brew --prefix python@3.12)/bin/python3.12"
if [ -x "$PY" ] && [ "$("$PY" -c 'import sys;print(sys.version_info[:2]==(3,12))')" != "True" ]; then
  mv "$VENV" "$VENV-$(date +%Y%m%d%H%M)"
fi
[ -x "$PY" ] || "$PY312" -m venv "$VENV"
"$PY" -m pip install -q --upgrade pip
"$PY" -m pip install -q -r "$BACKEND/requirements-dev.txt" -r "$BACKEND/requirements-real.txt"

passo "Voz Kokoro pt-BR"
"$PY" -m pip install -q -r "$BACKEND/requirements-voice-mac.txt"
(cd "$BACKEND" && PYTORCH_ENABLE_MPS_FALLBACK=1 HF_HUB_DISABLE_XET=1 "$PY" -c \
  "from kokoro import KPipeline; p=KPipeline(lang_code='p', repo_id='hexgrad/Kokoro-82M'); p.load_voice('pf_dora'); print('voz pronta')")

passo "Ollama + modelo do tutor ($MODELO)"
command -v ollama >/dev/null || brew install ollama
pgrep -x ollama >/dev/null || (ollama serve >/dev/null 2>&1 &)
sleep 3
ollama pull "$MODELO"

passo "Modelo de transcricao"
HF_HUB_DISABLE_XET=1 "$PY" -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8'); print('faster-whisper pronto')"

passo "Checklist"
(cd "$BACKEND" && NEKOMIND_TUTOR_MODEL="$MODELO" "$PY" -m app.devtools.preflight --voz kokoro)
echo; echo "Pronto. Ensaie com: bash scripts/apresentar.sh"

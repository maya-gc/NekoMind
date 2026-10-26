#!/usr/bin/env bash
# Install and cache the optional local pt-BR voice in the backend environment.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$ROOT/backend/.venv/bin/python"

if [ "$(uname -s)" != "Darwin" ]; then
  echo "A voz local do MVP requer macOS." >&2
  exit 1
fi
if [ ! -x "$PYTHON" ]; then
  echo "Prepare o backend primeiro: bash scripts/setup_backend.sh" >&2
  exit 1
fi
if ! command -v espeak-ng >/dev/null 2>&1; then
  echo "Instale o fonemizador local: brew install espeak-ng" >&2
  exit 1
fi

"$PYTHON" -m pip install -r "$ROOT/backend/requirements-voice-mac.txt"
PYTORCH_ENABLE_MPS_FALLBACK=1 HF_HUB_DISABLE_XET=1 HF_HUB_OFFLINE=0 \
  "$PYTHON" -c 'from kokoro import KPipeline; p = KPipeline(lang_code="p", repo_id="hexgrad/Kokoro-82M", device="mps"); p.load_voice("pf_dora")'
PYTORCH_ENABLE_MPS_FALLBACK=1 HF_HUB_OFFLINE=1 \
  "$PYTHON" -c 'from kokoro import KPipeline; p = KPipeline(lang_code="p", repo_id="hexgrad/Kokoro-82M", device="mps"); p.load_voice("pf_dora")'

echo "Voz Kokoro pt-BR pronta para executar offline no Mac."

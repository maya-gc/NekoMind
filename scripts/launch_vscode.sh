#!/usr/bin/env bash
# launch_vscode.sh - Abre o workspace nekomind no VS Code portatil.
#
# Localiza o repositório dinamicamente, exporta IDF_PATH/IDF_TOOLS_PATH,
# carrega export.sh (quando disponível) e abre a raiz como workspace.
set -euo pipefail

# 1. Raiz do repositorio (este script fica em <raiz>/scripts).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 2. Ambiente ESP-IDF (nao fatal se ainda nao instalado).
export IDF_PATH="$ROOT/esp-idf"
export IDF_TOOLS_PATH="$ROOT/tools"
if [ -f "$IDF_PATH/export.sh" ]; then
  # shellcheck source=/dev/null
  source "$IDF_PATH/export.sh" >/dev/null 2>&1 || true
fi

# 3. Localizar o binario do VS Code portatil.
VSCODE_BIN="$(find "$ROOT/vscode-portable" -maxdepth 3 -type f \( -name 'code' -o -name 'Code.exe' \) 2>/dev/null | head -n1)"

if [ -z "$VSCODE_BIN" ] || [ ! -x "$VSCODE_BIN" ]; then
  echo "ERRO: binario do VS Code portatil nao encontrado em $ROOT/vscode-portable"
  echo "Baixe e extraia em vscode-portable/ (ver vscode-portable/README.md)."
  exit 1
fi

echo ">> Abrindo workspace no VS Code portatil: $VSCODE_BIN"
exec "$VSCODE_BIN" "$ROOT"
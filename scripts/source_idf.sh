#!/usr/bin/env bash
# source_idf.sh - Configura o ambiente ESP-IDF para a sessao atual.
#
# Uso:
#   source scripts/source_idf.sh
#   cd iot/nekomind_firmware && idf.py build
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export IDF_PATH="$ROOT/esp-idf"
export IDF_TOOLS_PATH="$ROOT/tools"

if [ ! -f "$IDF_PATH/export.sh" ]; then
  echo "AVISO: $IDF_PATH/export.sh nao encontrado."
  echo "Execute antes: bash scripts/setup_espidf_portable.sh"
  return 1 2>/dev/null || exit 1
fi

# shellcheck source=/dev/null
source "$IDF_PATH/export.sh"

echo "== Ambiente ESP-IDF pronto =="
echo "  IDF_PATH=$IDF_PATH"
echo "  IDF_TOOLS_PATH=$IDF_TOOLS_PATH"
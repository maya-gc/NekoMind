#!/usr/bin/env bash
# setup_espidf_portable.sh - Instala ESP-IDF e toolchains dentro do monorepo
# (nekomind/esp-idf e nekomind/tools), sem instalar nada globalmente.
#
# Uso:
#   bash scripts/setup_espidf_portable.sh [versao_do_esp_idf]
#   Ex.: bash scripts/setup_espidf_portable.sh v5.3.1
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ESP_IDF_DIR="$ROOT/esp-idf"
TOOLS_DIR="$ROOT/tools"
export IDF_TOOLS_PATH="$TOOLS_DIR"

ESP_IDF_VERSION="${1:-v5.3.1}"
ESP_IDF_REPO="https://github.com/espressif/esp-idf.git"

if command -v git >/dev/null 2>&1; then
  : # ok
else
  echo "ERRO: git nao encontrado. Instale o Git antes de prosseguir."
  exit 1
fi

mkdir -p "$TOOLS_DIR"

if [ ! -d "$ESP_IDF_DIR/.git" ]; then
  echo ">> Clonando ESP-IDF ${ESP_IDF_VERSION} em $ESP_IDF_DIR ..."
  git clone --depth 1 --branch "$ESP_IDF_VERSION" --recursive --shallow-submodules \
    --jobs 8 "$ESP_IDF_REPO" "$ESP_IDF_DIR"
else
  echo ">> esp-idf ja presente em $ESP_IDF_DIR"
fi

echo ">> Instalando toolchains em $IDF_TOOLS_PATH ..."
if [ ! -f "$ESP_IDF_DIR/install.sh" ]; then
  echo "ERRO: install.sh nao encontrado em $ESP_IDF_DIR"
  exit 1
fi

if command -v bash >/dev/null 2>&1; then
  (cd "$ESP_IDF_DIR" && bash install.sh esp32s3)
else
  (cd "$ESP_IDF_DIR" && ./install.sh esp32s3)
fi

echo
echo "== ESP-IDF instalado =="
echo "  IDF_PATH       = $ESP_IDF_DIR"
echo "  IDF_TOOLS_PATH = $IDF_TOOLS_PATH"
echo "  Ative com: source scripts/source_idf.sh"
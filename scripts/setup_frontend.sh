#!/usr/bin/env bash
# setup_frontend.sh - Cria o venv do frontend Streamlit e instala dependencias.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONT_DIR="$ROOT/frontend/streamlit"
VENV_DIR="$FRONT_DIR/.venv"

cd "$FRONT_DIR"

if [ ! -d "$VENV_DIR" ]; then
  echo ">> Criando venv em $VENV_DIR ..."
  python3 -m venv "$VENV_DIR"
fi

echo ">> Instalando dependencias ..."
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r requirements.txt

echo
echo "== Frontend pronto =="
echo "  Rode: bash scripts/run_frontend.sh"
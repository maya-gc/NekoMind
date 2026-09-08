#!/usr/bin/env bash
# setup_backend.sh - Cria o venv do backend e instala as dependencias.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT/backend"
VENV_DIR="$BACKEND_DIR/.venv"

cd "$BACKEND_DIR"

if [ ! -d "$VENV_DIR" ]; then
  echo ">> Criando venv em $VENV_DIR ..."
  python3 -m venv "$VENV_DIR"
fi

echo ">> Instalando dependencias ..."
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r requirements.txt

echo
echo "== Backend pronto =="
echo "  Ative: source $VENV_DIR/bin/activate"
echo "  Rode:  bash scripts/run_backend.sh"
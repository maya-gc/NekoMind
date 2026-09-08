#!/usr/bin/env bash
# run_tests.sh - Executa os testes pytest do backend.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT/backend"
VENV_DIR="$BACKEND_DIR/.venv"
PYTHON="$VENV_DIR/bin/python"

if [ ! -x "$PYTHON" ]; then
  echo "Venv nao encontrado. Execute antes: bash scripts/setup_backend.sh"
  exit 1
fi

cd "$BACKEND_DIR"
exec "$PYTHON" -m pytest -v
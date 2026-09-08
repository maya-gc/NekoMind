#!/usr/bin/env bash
# run_frontend.sh - Sobe o dashboard Streamlit em http://127.0.0.1:8501
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONT_DIR="$ROOT/frontend/streamlit"
VENV_DIR="$FRONT_DIR/.venv"
PYTHON="$VENV_DIR/bin/python"

if [ ! -x "$PYTHON" ]; then
  echo "Venv nao encontrado. Execute antes: bash scripts/setup_frontend.sh"
  exit 1
fi

cd "$FRONT_DIR"
exec "$PYTHON" -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
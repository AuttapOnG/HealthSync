#!/usr/bin/env bash
set -euo pipefail

VENV_DIR=".venv"

if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment in $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python -m pip install -r requirements-poc.txt

echo
echo "Done. Next steps:"
echo "  1. cp .env.example .env   # then fill in values (never commit .env)"
echo "  2. source $VENV_DIR/bin/activate"
echo "  3. python -m pytest"

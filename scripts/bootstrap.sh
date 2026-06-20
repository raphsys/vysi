#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -m venv "$ROOT/.vysi"
"$ROOT/.vysi/bin/python" -m pip install --upgrade pip setuptools wheel
"$ROOT/.vysi/bin/python" -m pip install -e "$ROOT[dev]"
echo "Environnement prêt : $ROOT/.vysi"

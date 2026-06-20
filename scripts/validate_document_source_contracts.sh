#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.vysi/bin/python"
if [[ ! -x "$PY" ]]; then PY="${PYTHON:-python3}"; fi
cd "$ROOT"
PYTHONPATH="$ROOT/src" "$PY" tools/validate_document_source_contracts.py --root "$ROOT"

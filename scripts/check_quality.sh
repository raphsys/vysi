#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.vysi/bin/python"
cd "$ROOT"
"$PY" -m compileall -q src tests tools
"$PY" -m ruff check src tests tools
"$PY" -m mypy src/vysi

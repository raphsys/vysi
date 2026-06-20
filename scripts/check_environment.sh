#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.vysi/bin/python"
[[ -x "$PY" ]] || { echo "Environnement absent : $PY" >&2; exit 1; }
"$PY" - <<'PY'
from __future__ import annotations
import sys
from importlib.metadata import version
assert (3, 10) <= sys.version_info[:2] < (3, 14), sys.version
print(f"Python : {sys.version.split()[0]}")
print(f"Vysi   : {version('vysi')}")
PY
"$PY" -m pip check

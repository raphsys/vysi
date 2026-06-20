#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if command -v tree >/dev/null 2>&1; then
  tree -a -I '.git|.vysi|.vysi_test|.venv|__pycache__|.pytest_cache|.mypy_cache|.ruff_cache|*.egg-info|runtime/results/*|runtime/tmp/*|runtime/audit/*' .
else
  find . \
    \( -type d \( -name .git -o -name .vysi -o -name .vysi_test -o -name .venv -o -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache -o -name .ruff_cache \) -prune \) \
    -o -type f -print | sort
fi

#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${VYSI_PYTHON:-$ROOT/.vysi/bin/python}"
"$PY" "$ROOT/tools/generate_project_manifest.py" \
  --root "$ROOT" \
  --version "0.6.1" \
  --revision "DOCUMENT_SOURCE_NATIVE_PROPERTY_HOTFIX"

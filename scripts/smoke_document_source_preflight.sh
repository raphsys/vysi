#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.vysi/bin/python"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
SOURCE="$ROOT/runtime/tmp/preflight_${STAMP}.txt"
OUTPUT="$ROOT/runtime/results/document_source"
mkdir -p "$(dirname "$SOURCE")" "$OUTPUT"
printf 'Vysi DS00-DS06\n' > "$SOURCE"
CHECKPOINT="$($PY -m vysi.document_source.cli preflight --source "$SOURCE" --output "$OUTPUT")"
[[ -f "$CHECKPOINT/PREFLIGHT_COMPLETE" ]] || { echo "Préflight incomplet" >&2; exit 1; }
[[ ! -e "$CHECKPOINT/COMMITTED" ]] || { echo "COMMITTED interdit avant DS15" >&2; exit 1; }
PYTHONPATH="$ROOT/src" "$PY" "$ROOT/tools/validate_preflight_checkpoint.py" "$CHECKPOINT"
echo "Smoke DS00-DS06 réussi : $CHECKPOINT"

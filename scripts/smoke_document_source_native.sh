#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.vysi/bin/python"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
SOURCE="$ROOT/runtime/tmp/native_${STAMP}.txt"
OUTPUT="$ROOT/runtime/results/document_source"
mkdir -p "$(dirname "$SOURCE")" "$OUTPUT"
printf 'Vysi DS00-DS09\nExtraction native déterministe.\n' > "$SOURCE"
CHECKPOINT="$($PY -m vysi.document_source.cli native --source "$SOURCE" --output "$OUTPUT")"
[[ -f "$CHECKPOINT/PREFLIGHT_COMPLETE" ]] || { echo "Préflight incomplet" >&2; exit 1; }
[[ -f "$CHECKPOINT/NATIVE_COMPLETE" ]] || { echo "Extraction native incomplète" >&2; exit 1; }
[[ ! -e "$CHECKPOINT/COMMITTED" ]] || { echo "COMMITTED interdit avant DS15" >&2; exit 1; }
find "$CHECKPOINT/native" -name native_document.json -print -quit | grep -q . || { echo "NativeDocument absent" >&2; exit 1; }
PYTHONPATH="$ROOT/src" "$PY" "$ROOT/tools/validate_preflight_checkpoint.py" "$CHECKPOINT"
echo "Smoke DS00-DS09 réussi : $CHECKPOINT"

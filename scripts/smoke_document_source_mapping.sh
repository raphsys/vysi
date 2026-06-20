#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.vysi/bin/python"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
SOURCE="$ROOT/runtime/tmp/mapping_${STAMP}.txt"
OUTPUT="$ROOT/runtime/results/document_source"
mkdir -p "$(dirname "$SOURCE")" "$OUTPUT"
printf 'Vysi DS12\nCartographie des représentations.\n' > "$SOURCE"
CHECKPOINT="$($PY -m vysi.document_source.cli mapping --source "$SOURCE" --output "$OUTPUT")"
[[ -f "$CHECKPOINT/PREFLIGHT_COMPLETE" ]] || { echo "Préflight incomplet" >&2; exit 1; }
[[ -f "$CHECKPOINT/NATIVE_COMPLETE" ]] || { echo "Extraction native incomplète" >&2; exit 1; }
[[ -f "$CHECKPOINT/IR_COMPLETE" ]] || { echo "Projection IR incomplète" >&2; exit 1; }
[[ -f "$CHECKPOINT/MAPPING_COMPLETE" ]] || { echo "Cartographie incomplète" >&2; exit 1; }
[[ ! -e "$CHECKPOINT/QUALITY_COMPLETE" ]] || { echo "QUALITY_COMPLETE prématuré au terme de DS12" >&2; exit 1; }
[[ ! -e "$CHECKPOINT/COMMITTED" ]] || { echo "COMMITTED interdit avant DS15" >&2; exit 1; }
find "$CHECKPOINT/mapping" -name representation_mapping_catalog.json -print -quit | grep -q . || {
  echo "RepresentationMappingCatalog absent" >&2
  exit 1
}
PYTHONPATH="$ROOT/src" "$PY" "$ROOT/tools/validate_preflight_checkpoint.py" "$CHECKPOINT"
echo "Smoke DS00-DS10, DS12 réussi : $CHECKPOINT"

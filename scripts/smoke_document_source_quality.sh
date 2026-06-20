#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.vysi/bin/python"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
SOURCE="$ROOT/runtime/tmp/quality_${STAMP}.txt"
OUTPUT="$ROOT/runtime/results/document_source"
mkdir -p "$(dirname "$SOURCE")" "$OUTPUT"
printf 'Vysi DS12-DS13\nCartographie et fidélité.\n' > "$SOURCE"
CHECKPOINT="$($PY -m vysi.document_source.cli quality --source "$SOURCE" --output "$OUTPUT")"
[[ -f "$CHECKPOINT/PREFLIGHT_COMPLETE" ]] || { echo "Préflight incomplet" >&2; exit 1; }
[[ -f "$CHECKPOINT/NATIVE_COMPLETE" ]] || { echo "Extraction native incomplète" >&2; exit 1; }
[[ -f "$CHECKPOINT/IR_COMPLETE" ]] || { echo "Projection IR incomplète" >&2; exit 1; }
[[ -f "$CHECKPOINT/MAPPING_COMPLETE" ]] || { echo "Cartographie incomplète" >&2; exit 1; }
[[ -f "$CHECKPOINT/QUALITY_COMPLETE" ]] || { echo "Couverture/préservation incomplète" >&2; exit 1; }
[[ ! -e "$CHECKPOINT/COMMITTED" ]] || { echo "COMMITTED interdit avant DS15" >&2; exit 1; }
find "$CHECKPOINT/mapping" -name representation_mapping_catalog.json -print -quit | grep -q . || { echo "RepresentationMappingCatalog absent" >&2; exit 1; }
find "$CHECKPOINT/quality" -name feature_coverage_report.json -print -quit | grep -q . || { echo "FeatureCoverageReport absent" >&2; exit 1; }
find "$CHECKPOINT/quality" -name preservation_report.json -print -quit | grep -q . || { echo "PreservationReport absent" >&2; exit 1; }
PYTHONPATH="$ROOT/src" "$PY" "$ROOT/tools/validate_preflight_checkpoint.py" "$CHECKPOINT"
echo "Smoke DS00-DS10, DS12-DS13 réussi : $CHECKPOINT"

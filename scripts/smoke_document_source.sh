#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.vysi/bin/python"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
SOURCE="$ROOT/runtime/tmp/smoke_${STAMP}.txt"
OUTPUT="$ROOT/runtime/results/document_source"
mkdir -p "$(dirname "$SOURCE")" "$OUTPUT"
printf 'Titre Vysi\n\nPremière unité DOCUMENT_SOURCE.\n' > "$SOURCE"
PACKAGE="$($PY -m vysi.document_source.cli ingest "$SOURCE" --output "$OUTPUT")"
[[ -f "$PACKAGE/COMMITTED" ]] || { echo "Package non commité" >&2; exit 1; }
echo "Smoke test réussi : $PACKAGE"

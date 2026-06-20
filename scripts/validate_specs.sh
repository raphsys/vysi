#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC="$ROOT/docs/specifications/document_source_v2"
SCHEMAS="$ROOT/src/vysi/document_source/schemas/v2"
for i in $(seq -w 0 28); do compgen -G "$SPEC/${i}_*.md" >/dev/null || { echo "Document normatif manquant: $i" >&2; exit 1; }; done
for i in $(seq -w 0 15); do compgen -G "$SPEC/subunits/DS${i}_*.md" >/dev/null || { echo "Sous-unité manquante: DS$i" >&2; exit 1; }; done
[[ -f "$SCHEMAS/SCHEMA_REGISTRY.json" ]] || { echo "Registre de schémas manquant" >&2; exit 1; }
COUNT="$(find "$SCHEMAS" -maxdepth 1 -name '*.schema.json' | wc -l)"
[[ "$COUNT" -ge 41 ]] || { echo "Schémas insuffisants: $COUNT" >&2; exit 1; }
ERRORS="$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["codes"]))' "$SPEC/catalogs/ERROR_CODES.json")"
echo "Spécification gelée valide : 29 documents normatifs, 16 sous-unités, $COUNT schémas, $ERRORS codes d’erreur."

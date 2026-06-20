#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.vysi/bin/python"
"$PY" - "$ROOT" <<'PYCODE'
from __future__ import annotations
import json
import sys
from pathlib import Path
root = Path(sys.argv[1])
required = [
    'src/vysi/document_source/contracts',
    'src/vysi/document_source/contracts_v2',
    'src/vysi/document_source/adapters/containers',
    'src/vysi/document_source/adapters/native',
    'src/vysi/document_source/container_v2',
    'src/vysi/document_source/native_v2',
    'src/vysi/document_source/technical_ir_v2',
    'src/vysi/document_source/representation_v2',
    'src/vysi/document_source/quality_v2',
    'src/vysi/document_source/subunits',
    'src/vysi/document_source/pipeline',
    'src/vysi/document_source/services',
    'src/vysi/document_source/schemas/v2',
    'docs/specifications/document_source_v2/subunits',
    'docs/specifications/document_source_v2/profiles',
    'docs/specifications/document_source_v2/catalogs',
    'docs/specifications/document_source_v2/matrices',
    'tests',
    'runtime/results',
]
missing = [item for item in required if not (root / item).exists()]
if missing:
    raise SystemExit(f"Structure incomplète : {missing}")
registry = json.loads((root / 'src/vysi/document_source/schemas/v2/SCHEMA_REGISTRY.json').read_text(encoding='utf-8'))
subunits = list((root / 'docs/specifications/document_source_v2/subunits').glob('DS*.md'))
profiles = list((root / 'docs/specifications/document_source_v2/profiles').glob('*.md'))
print(f"Structure valide : {len(required)} groupes, {len(subunits)} sous-unités, {len(profiles)} profils, {len(registry['schemas'])} schémas.")
PYCODE

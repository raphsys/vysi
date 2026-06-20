#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.vysi/bin/python"
"$PY" - "$ROOT" <<'PY'
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path
root = Path(sys.argv[1])
manifest = json.loads((root / 'PROJECT_MANIFEST.json').read_text(encoding='utf-8'))
errors: list[str] = []
for item in manifest['files']:
    path = root / item['path']
    if not path.is_file():
        errors.append(f"absent: {item['path']}")
        continue
    payload = path.read_bytes()
    if len(payload) != item['bytes']:
        errors.append(f"taille: {item['path']}")
    if hashlib.sha256(payload).hexdigest() != item['sha256']:
        errors.append(f"sha256: {item['path']}")
if errors:
    raise SystemExit("MANIFESTE INVALIDE\n- " + "\n- ".join(errors))
print(f"Manifest projet valide : {manifest['file_count']} fichiers, version {manifest['project_version']}.")
PY

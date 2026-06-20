#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
./scripts/check_environment.sh
./scripts/check_structure.sh
./scripts/validate_specs.sh
./scripts/validate_project_manifest.sh
./scripts/check_quality.sh
./scripts/run_tests.sh
./scripts/validate_document_source_contracts.sh
echo "VYSI 0.6.1 — DOCUMENT_SOURCE DS00–DS10, DS12–DS13 : VALIDATION COMPLETE"

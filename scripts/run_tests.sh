#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.vysi/bin/python"
cd "$ROOT"

mapfile -d '' TEST_FILES < <(
  find tests -type f -name 'test_*.py' -print0 | sort -z
)

[[ "${#TEST_FILES[@]}" -gt 0 ]] || {
  echo "Aucun fichier de tests trouvé." >&2
  exit 1
}

PASSED_TOTAL=0
for test_file in "${TEST_FILES[@]}"; do
  printf '\n=== %s ===\n' "$test_file"
  output="$(PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 "$PY" -m pytest -q "$test_file")"
  printf '%s\n' "$output"
  passed="$(printf '%s\n' "$output" | grep -Eo '[0-9]+ passed' | tail -1 | awk '{print $1}')"
  [[ -n "$passed" ]] || {
    echo "Impossible de déterminer le nombre de tests réussis pour $test_file" >&2
    exit 1
  }
  PASSED_TOTAL=$((PASSED_TOTAL + passed))
done

printf '\n%d tests passants dans %d fichiers de tests.\n' \
  "$PASSED_TOTAL" "${#TEST_FILES[@]}"

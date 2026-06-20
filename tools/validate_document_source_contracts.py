from __future__ import annotations

import argparse
import json
from pathlib import Path

from vysi.document_source.contracts_v2.validation import ContractValidationError, SchemaStore


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    schema_dir = root / "src/vysi/document_source/schemas/v2"
    examples_dir = root / "docs/specifications/document_source_v2/examples"
    index = json.loads((examples_dir / "EXAMPLE_INDEX.json").read_text(encoding="utf-8"))
    store = SchemaStore(schema_dir)
    valid_count = 0
    invalid_count = 0
    for item in index["valid"]:
        store.load_and_validate(str(item["schema"]), examples_dir / "valid" / str(item["file"]))
        valid_count += 1
    for item in index["invalid"]:
        path = examples_dir / "invalid" / str(item["file"])
        instance = json.loads(path.read_text(encoding="utf-8"))
        try:
            store.validate(str(item["schema"]), instance)
        except ContractValidationError:
            invalid_count += 1
        else:
            raise SystemExit(f"Invalid example unexpectedly accepted: {path}")
    print(
        f"DOCUMENT_SOURCE contracts valid: {len(store.schema_keys)} schemas, {valid_count} valid examples, {invalid_count} rejected invalid examples."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

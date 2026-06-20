from __future__ import annotations

import json
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")


def test_all_schemas_are_valid() -> None:
    root = Path(__file__).resolve().parents[1] / "src/vysi/document_source/schemas"
    registry = json.loads((root / "SCHEMA_REGISTRY.json").read_text())
    assert len(registry["schemas"]) >= 10
    for item in registry["schemas"]:
        schema = json.loads((root / item["path"]).read_text())
        jsonschema.Draft202012Validator.check_schema(schema)

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs/specifications/document_source_v2"


def test_all_subunit_contracts_exist() -> None:
    files = {path.name[:4] for path in (SPEC / "subunits").glob("DS*.md")}
    assert files == {f"DS{i:02d}" for i in range(16)}


def test_required_normative_documents_exist() -> None:
    for index in range(33):
        assert list(SPEC.glob(f"{index:02d}_*.md")), index


def test_schema_registry_has_strict_schemas() -> None:
    schema_dir = ROOT / "src/vysi/document_source/schemas/v2"
    registry = json.loads((schema_dir / "SCHEMA_REGISTRY.json").read_text(encoding="utf-8"))
    assert len(registry["schemas"]) >= 30
    for meta in registry["schemas"].values():
        schema = json.loads((schema_dir / meta["path"]).read_text(encoding="utf-8"))
        if schema.get("type") == "object" and schema["$id"].split("/")[-1] != "common.schema.json":
            assert schema.get("additionalProperties") is False


def test_decision_register_has_all_status_sections() -> None:
    text = (SPEC / "20_DECISION_REGISTER.md").read_text(encoding="utf-8")
    for heading in ["DECIDED", "DEFERRED", "FORBIDDEN", "EXTENSION_POINT"]:
        assert f"## {heading}" in text

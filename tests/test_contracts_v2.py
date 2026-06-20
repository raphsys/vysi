from __future__ import annotations

import json
from pathlib import Path

import pytest

from vysi.document_source.contracts_v2.canonical import content_hash
from vysi.document_source.contracts_v2.identities import stable_id
from vysi.document_source.contracts_v2.models import (
    ContractReference,
    RepresentationSlot,
    RepresentationState,
)
from vysi.document_source.contracts_v2.validation import ContractValidationError, SchemaStore

ROOT = Path(__file__).resolve().parents[1]


def store() -> SchemaStore:
    return SchemaStore(ROOT / "src/vysi/document_source/schemas/v2")


def test_all_valid_examples_validate() -> None:
    index_path = ROOT / "docs/specifications/document_source_v2/examples/EXAMPLE_INDEX.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    schemas = store()
    for item in index["valid"]:
        schemas.load_and_validate(item["schema"], index_path.parent / "valid" / item["file"])


def test_all_invalid_examples_are_rejected() -> None:
    index_path = ROOT / "docs/specifications/document_source_v2/examples/EXAMPLE_INDEX.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    schemas = store()
    for item in index["invalid"]:
        value = json.loads(
            (index_path.parent / "invalid" / item["file"]).read_text(encoding="utf-8")
        )
        with pytest.raises(ContractValidationError):
            schemas.validate(item["schema"], value)


def test_representation_slot_invariants() -> None:
    ref = ContractReference("contracts/a.json", "0" * 64, "x.y", "2.0.0", "contract_example001")
    RepresentationSlot(RepresentationState.AVAILABLE, ref)
    RepresentationSlot(RepresentationState.NOT_REQUESTED, None)
    with pytest.raises(ValueError):
        RepresentationSlot(RepresentationState.AVAILABLE, None)
    with pytest.raises(ValueError):
        RepresentationSlot(RepresentationState.UNSUPPORTED, ref)


def test_content_hash_ignores_ephemeral_header_fields() -> None:
    first = {"header": {"content_hash": "a", "created_at": "t1", "contract_id": "x"}, "value": 1}
    second = {"header": {"content_hash": "b", "created_at": "t2", "contract_id": "x"}, "value": 1}
    assert content_hash(first) == content_hash(second)


def test_content_hash_rejects_non_finite_float() -> None:
    with pytest.raises(ValueError):
        content_hash({"value": float("nan")})


def test_stable_id_is_deterministic() -> None:
    assert stable_id("document", {"x": 1}) == stable_id("document", {"x": 1})
    assert stable_id("document", {"x": 1}) != stable_id("document", {"x": 2})


def test_valid_examples_have_canonical_content_hashes() -> None:
    index_path = ROOT / "docs/specifications/document_source_v2/examples/EXAMPLE_INDEX.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    for item in index["valid"]:
        value = json.loads((index_path.parent / "valid" / item["file"]).read_text(encoding="utf-8"))
        header = value.get("header") if isinstance(value, dict) else None
        if isinstance(header, dict):
            assert header["content_hash"] == content_hash(value), item["file"]

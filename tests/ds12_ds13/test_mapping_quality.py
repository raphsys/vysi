from __future__ import annotations

import json
from pathlib import Path

import pytest
from ds00_ds06.helpers import request_for
from helpers import make_docx, make_xlsx

from vysi.document_source.contracts_v2.identities import stable_id
from vysi.document_source.execution.coordinator import run_ir, run_quality
from vysi.document_source.execution.errors import StageFailure
from vysi.document_source.quality_v2 import QualityError, validate_quality_invariants
from vysi.document_source.representation_v2 import MappingError, validate_mapping_invariants


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _document_dir(root: Path, name: str) -> Path:
    return next((root / name).glob("document_*"))


def test_text_quality_maps_binary_native_and_ir_without_commit(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("alpha\nbeta\n", encoding="utf-8")
    result = run_quality(request_for(source), tmp_path / "out")
    mapping = _json(
        _document_dir(result.workspace, "mapping") / "representation_mapping_catalog.json"
    )
    coverage = _json(_document_dir(result.workspace, "quality") / "feature_coverage_report.json")
    preservation = _json(_document_dir(result.workspace, "quality") / "preservation_report.json")
    assert (result.workspace / "MAPPING_COMPLETE").is_file()
    assert (result.workspace / "QUALITY_COMPLETE").is_file()
    assert not (result.workspace / "COMMITTED").exists()
    assert any(
        item["source_layer"] == "binary" and item["target_layer"] == "container"
        for item in mapping["mappings"]
    )
    assert any(
        item["source_layer"] == "container" and item["target_layer"] == "native"
        for item in mapping["mappings"]
    )
    assert any(
        item["source_layer"] == "native" and item["target_layer"] == "technical_ir"
        for item in mapping["mappings"]
    )
    assert coverage["axis_scores"]["binary"] == 1.0
    assert coverage["axis_scores"]["structural"] == 1.0
    assert coverage["axis_scores"]["visual"] is None
    assert preservation["roundtrip_risk"] == "none"
    assert preservation["losses"] == []


def test_docx_mapping_uses_container_source_addresses(tmp_path: Path) -> None:
    source = tmp_path / "sample.docx"
    make_docx(source)
    result = run_quality(request_for(source), tmp_path / "out")
    mapping = _json(
        _document_dir(result.workspace, "mapping") / "representation_mapping_catalog.json"
    )
    assert any(
        item["source_layer"] == "binary" and item["target_layer"] == "container"
        for item in mapping["mappings"]
    )
    assert any(
        item["source_layer"] == "container" and item["target_layer"] == "native"
        for item in mapping["mappings"]
    )
    assert all(0.0 <= item["confidence"] <= 1.0 for item in mapping["mappings"])


def test_formula_coverage_is_computationally_complete_without_execution(tmp_path: Path) -> None:
    source = tmp_path / "sample.xlsx"
    make_xlsx(source)
    result = run_quality(request_for(source), tmp_path / "out")
    coverage = _json(_document_dir(result.workspace, "quality") / "feature_coverage_report.json")
    formula = next(item for item in coverage["items"] if item["feature"] == "formula")
    assert formula["encountered"] == 1
    assert formula["projected"] == 1
    assert formula["omitted"] == 0
    assert coverage["axis_scores"]["computational"] == 1.0


def test_ir_checkpoint_resumes_through_ds13(tmp_path: Path) -> None:
    source = tmp_path / "resume.txt"
    source.write_text("resume", encoding="utf-8")
    request = request_for(source)
    ir = run_ir(request, tmp_path / "out")
    result = run_quality(request, tmp_path / "unused", resume_from=ir.workspace)
    assert result.workspace == ir.workspace
    checkpoint = _json(result.workspace / "execution/checkpoint_manifest.json")
    assert {"DS12", "DS13"} <= set(checkpoint["completed_nodes"])


def test_mapping_and_quality_are_deterministic(tmp_path: Path) -> None:
    source = tmp_path / "stable.txt"
    source.write_text("stable\n", encoding="utf-8")
    request = request_for(source)
    first = run_quality(request, tmp_path / "out1")
    second = run_quality(request, tmp_path / "out2")
    first_mapping = _json(
        _document_dir(first.workspace, "mapping") / "representation_mapping_catalog.json"
    )
    second_mapping = _json(
        _document_dir(second.workspace, "mapping") / "representation_mapping_catalog.json"
    )
    first_coverage = _json(
        _document_dir(first.workspace, "quality") / "feature_coverage_report.json"
    )
    second_coverage = _json(
        _document_dir(second.workspace, "quality") / "feature_coverage_report.json"
    )
    assert first_mapping["header"]["content_hash"] == second_mapping["header"]["content_hash"]
    assert first_coverage["header"]["content_hash"] == second_coverage["header"]["content_hash"]


def test_ds12_rejects_tampered_ir(tmp_path: Path) -> None:
    source = tmp_path / "tampered.txt"
    source.write_text("before", encoding="utf-8")
    request = request_for(source)
    ir = run_ir(request, tmp_path / "out")
    ir_path = _document_dir(ir.workspace, "ir") / "technical_document_ir.json"
    value = _json(ir_path)
    value["units"][0]["kind"] = "changed"
    ir_path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(StageFailure, match="Hash"):
        run_quality(request, tmp_path / "unused", resume_from=ir.workspace)


def test_mapping_invariants_reject_unknown_source() -> None:
    identity = {
        "document_id": "document_example",
        "source_layer": "native",
        "source_ids": ("missing",),
        "target_layer": "technical_ir",
        "target_ids": ("ir_1",),
        "relation": "projects_to",
        "method": "test",
        "producer": "vysi.document_source.ds12",
        "producer_version": "0.8.1",
    }
    body = {
        "document_id": "document_example",
        "mappings": [
            {
                "mapping_id": stable_id("mapping", identity),
                "source_layer": "native",
                "source_ids": ["missing"],
                "target_layer": "technical_ir",
                "target_ids": ["ir_1"],
                "relation": "projects_to",
                "cardinality": "one_to_one",
                "exactness": "exact",
                "confidence": 1.0,
                "method": "test",
                "producer": "vysi.document_source.ds12",
                "producer_version": "0.8.1",
                "determinism": "deterministic",
                "evidence_refs": ["native/example.json"],
            }
        ],
    }
    with pytest.raises(MappingError, match="inconnues"):
        validate_mapping_invariants(
            body,
            layer_ids={"native": set(), "technical_ir": {"ir_1"}},
            producer_version="0.8.1",
        )


def test_quality_invariants_reject_duplicate_features() -> None:
    coverage = {
        "document_id": "document_example",
        "items": [
            {
                "feature": "x",
                "encountered": 1,
                "extracted": 1,
                "preserved": 1,
                "projected": 1,
                "rendered": 0,
                "opaque": 0,
                "approximated": 0,
                "unsupported": 0,
                "omitted": 0,
                "severity": "info",
                "evidence_refs": [],
            },
            {
                "feature": "x",
                "encountered": 1,
                "extracted": 1,
                "preserved": 1,
                "projected": 1,
                "rendered": 0,
                "opaque": 0,
                "approximated": 0,
                "unsupported": 0,
                "omitted": 0,
                "severity": "info",
                "evidence_refs": [],
            },
        ],
        "axis_scores": {"binary": 1.0},
    }
    preservation = {
        "document_id": "document_example",
        "transitions": [],
        "losses": [],
        "opaque_preserved_count": 0,
        "roundtrip_risk": "none",
    }
    with pytest.raises(QualityError, match="dupliquées"):
        validate_quality_invariants(coverage, preservation)


def test_legacy_ole_quality_declares_unsupported_semantic_decode(tmp_path: Path) -> None:
    from ds07_ds09.test_native_additional_formats import _minimal_cfb

    source = tmp_path / "legacy.doc"
    source.write_bytes(_minimal_cfb())
    result = run_quality(request_for(source), tmp_path / "out")
    coverage = _json(_document_dir(result.workspace, "quality") / "feature_coverage_report.json")
    preservation = _json(_document_dir(result.workspace, "quality") / "preservation_report.json")
    legacy = next(item for item in coverage["items"] if item["feature"] == "legacy_semantic_decode")
    assert legacy["unsupported"] == 1
    assert preservation["roundtrip_risk"] == "high"
    assert any(item["kind"] == "unsupported" for item in preservation["losses"])
    assert coverage["header"]["status"] == "review"


def test_quality_checkpoint_passes_reference_validator(tmp_path: Path) -> None:
    from vysi.document_source.execution.preflight_validation import validate_preflight

    source = tmp_path / "validated.txt"
    source.write_text("validated", encoding="utf-8")
    result = run_quality(request_for(source), tmp_path / "out")
    assert validate_preflight(result.workspace) == ()

from __future__ import annotations

import json
from pathlib import Path

from ds00_ds06.helpers import request_for
from ds07_ds09.test_native_property_names import _make_realistic_docx

from vysi.document_source.execution.coordinator import run_quality
from vysi.document_source.quality_v2.evaluate import (
    _combine_scores,
    _losses_from_measurement,
)
from vysi.document_source.quality_v2.models import FeatureMeasurement


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _document_dir(root: Path, name: str) -> Path:
    return next((root / name).glob("document_*"))


def test_ds10_projects_complete_style_and_metadata_catalogs(tmp_path: Path) -> None:
    source = tmp_path / "catalogs.docx"
    _make_realistic_docx(source)

    result = run_quality(request_for(source), tmp_path / "out")
    native_dir = _document_dir(result.workspace, "native")
    ir_dir = _document_dir(result.workspace, "ir")
    quality_dir = _document_dir(result.workspace, "quality")

    styles = _json(native_dir / "styles.json")
    metadata = _json(native_dir / "metadata.json")
    ir = _json(ir_dir / "technical_document_ir.json")
    coverage = _json(quality_dir / "feature_coverage_report.json")
    preservation = _json(quality_dir / "preservation_report.json")

    native_style_ids = {item["style_id"] for item in styles["styles"]}
    native_metadata_ids = {item["metadata_id"] for item in metadata["items"]}
    projected_style_ids = {
        source_id
        for unit in ir["units"]
        if unit["kind"] == "style_definition"
        for source_id in unit["source_native_ids"]
    }
    projected_metadata_ids = {
        source_id
        for unit in ir["units"]
        if unit["kind"] == "metadata"
        for source_id in unit["source_native_ids"]
    }

    assert native_style_ids
    assert native_metadata_ids
    assert projected_style_ids == native_style_ids
    assert projected_metadata_ids == native_metadata_ids
    assert all(unit["protected"] for unit in ir["units"] if unit["kind"] == "metadata")
    assert all(
        unit["protected"] for unit in ir["units"] if unit["kind"] == "style_definition"
    )

    style = next(item for item in coverage["items"] if item["feature"] == "native_style")
    metadata_item = next(
        item for item in coverage["items"] if item["feature"] == "native_metadata"
    )
    assert style["required"] == style["encountered"] == style["projected"]
    assert metadata_item["required"] == metadata_item["encountered"] == metadata_item["projected"]
    assert style["preservation_stage"] == "native_to_technical_ir"
    assert metadata_item["preservation_stage"] == "native_to_technical_ir"
    assert coverage["axis_scores"]["style"] == 1.0
    assert coverage["axis_scores"]["technical_semantic"] == 1.0
    assert not {
        loss["feature"] for loss in preservation["losses"]
    } & {"native_style", "native_metadata"}


def test_loss_uses_feature_preservation_stage_not_generic_axis() -> None:
    item = FeatureMeasurement(
        feature="container_part",
        axis="structural",
        preservation_stage="container_to_native",
        basis="test",
        encountered=1,
        required=0,
        extracted=1,
        preserved=1,
        projected=1,
        rendered=0,
        opaque=0,
        approximated=1,
        unsupported=0,
        omitted=0,
        severity="info",
        evidence_refs=("manifests/container/document_example.json",),
        preserved_refs=("part_example",),
        projected_refs=("part_example",),
        approximated_refs=("part_example",),
    )
    losses = _losses_from_measurement("document_example", item)
    assert len(losses) == 1
    assert losses[0].stage == "container_to_native"
    assert losses[0].feature == "container_part"


def test_score_is_not_applicable_when_projection_scope_is_empty() -> None:
    item = FeatureMeasurement(
        feature="optional_catalog",
        axis="style",
        preservation_stage="native_to_technical_ir",
        basis="test",
        encountered=6,
        required=0,
        extracted=6,
        preserved=6,
        projected=0,
        rendered=0,
        opaque=0,
        approximated=0,
        unsupported=0,
        omitted=0,
        severity="info",
        evidence_refs=("native/document_example/styles.json",),
        preserved_refs=tuple(f"style_{index}" for index in range(6)),
    )
    assert _combine_scores([item]) is None


def test_every_coverage_measurement_declares_scope_and_owner(tmp_path: Path) -> None:
    source = tmp_path / "coverage.docx"
    _make_realistic_docx(source)
    result = run_quality(request_for(source), tmp_path / "out")
    coverage = _json(
        _document_dir(result.workspace, "quality") / "feature_coverage_report.json"
    )
    allowed = {
        "binary_to_container",
        "container_to_native",
        "native_to_technical_ir",
        "native_to_rendered",
        "rendered_to_asset",
        "roundtrip",
    }
    for item in coverage["items"]:
        assert 0 <= item["required"] <= item["encountered"]
        assert item["omitted"] <= item["required"]
        assert item["preservation_stage"] in allowed
    container_part = next(
        item for item in coverage["items"] if item["feature"] == "container_part"
    )
    assert container_part["preservation_stage"] == "container_to_native"


def test_quality_invariants_reject_required_scope_over_encountered() -> None:
    from vysi.document_source.quality_v2 import QualityError, validate_quality_invariants

    coverage = {
        "document_id": "document_example",
        "items": [
            {
                "feature": "x",
                "axis": "style",
                "preservation_stage": "native_to_technical_ir",
                "basis": "test",
                "encountered": 1,
                "required": 2,
                "extracted": 1,
                "preserved": 1,
                "projected": 1,
                "rendered": 0,
                "opaque": 0,
                "approximated": 0,
                "unsupported": 0,
                "omitted": 0,
                "severity": "info",
                "evidence_refs": ["native/document_example/styles.json"],
            }
        ],
        "axis_scores": {},
    }
    preservation = {
        "document_id": "document_example",
        "transitions": [],
        "losses": [],
        "opaque_preserved_count": 0,
        "roundtrip_risk": "none",
    }
    try:
        validate_quality_invariants(coverage, preservation)
    except QualityError as exc:
        assert "Périmètre requis invalide" in str(exc)
    else:
        raise AssertionError("Le périmètre required > encountered devait être rejeté")

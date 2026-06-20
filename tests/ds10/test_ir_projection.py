from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from ds00_ds06.helpers import request_for
from helpers import make_docx, make_pptx, make_xlsx

from vysi.document_source.execution.coordinator import run_ir, run_native
from vysi.document_source.execution.errors import StageFailure
from vysi.document_source.technical_ir_v2 import (
    ProjectionError,
    project_document,
    validate_ir_invariants,
)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _ir_path(workspace: Path) -> Path:
    return next((workspace / "ir").glob("document_*/technical_document_ir.json"))


def _native_dir(workspace: Path) -> Path:
    return next(
        path
        for path in (workspace / "native").iterdir()
        if path.is_dir() and path.name.startswith("document_")
    )


def test_text_projection_is_traceable_and_has_no_final_commit(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("alpha\nbeta\n", encoding="utf-8")
    result = run_ir(request_for(source), tmp_path / "out")
    ir = _json(_ir_path(result.workspace))
    assert (result.workspace / "IR_COMPLETE").is_file()
    assert not (result.workspace / "COMMITTED").exists()
    lines = [unit for unit in ir["units"] if unit["kind"] == "text_line"]
    assert [unit["text"] for unit in lines] == ["alpha", "beta"]
    assert all(unit["origin"] == "native_projection" for unit in lines)
    assert all(unit["source_native_ids"] for unit in lines)


def test_docx_projection_preserves_hierarchy_and_text(tmp_path: Path) -> None:
    source = tmp_path / "sample.docx"
    make_docx(source)
    result = run_ir(request_for(source), tmp_path / "out")
    ir = _json(_ir_path(result.workspace))
    kinds = {unit["kind"] for unit in ir["units"]}
    assert {"paragraph", "text_span", "table", "table_row", "table_cell"} <= kinds
    assert any(unit["text"] == "Bonjour monde" for unit in ir["units"])
    assert any(unit["text"] == "Cellule" for unit in ir["units"])
    ids = {unit["unit_id"] for unit in ir["units"]}
    assert all(unit["parent_id"] is None or unit["parent_id"] in ids for unit in ir["units"])


def test_xlsx_formula_remains_protected_and_not_recalculated(tmp_path: Path) -> None:
    source = tmp_path / "sample.xlsx"
    make_xlsx(source)
    result = run_ir(request_for(source), tmp_path / "out")
    ir = _json(_ir_path(result.workspace))
    formula = next(unit for unit in ir["units"] if unit["kind"] == "formula")
    assert formula["text"] == "SUM(B2:B3)"
    assert formula["protected"] is True
    properties = {item["name"]: item["value"] for item in formula["technical_properties"]}
    assert properties["formula.recalculated"] is False
    assert properties["formula.dependency_refs"] == ["B2", "B3"]


def test_pptx_projection_keeps_slide_and_shape_without_semantic_title(tmp_path: Path) -> None:
    source = tmp_path / "sample.pptx"
    make_pptx(source)
    result = run_ir(request_for(source), tmp_path / "out")
    ir = _json(_ir_path(result.workspace))
    assert any(unit["kind"] == "slide" for unit in ir["units"])
    shape = next(unit for unit in ir["units"] if unit["kind"] == "text_shape")
    assert shape["text"] == "Titre"
    assert all(unit["kind"] != "title" for unit in ir["units"])


def test_native_checkpoint_resumes_through_ds10(tmp_path: Path) -> None:
    source = tmp_path / "resume.txt"
    source.write_text("resume", encoding="utf-8")
    request = request_for(source)
    native = run_native(request, tmp_path / "out")
    result = run_ir(request, tmp_path / "unused", resume_from=native.workspace)
    assert result.workspace == native.workspace
    assert (result.workspace / "IR_COMPLETE").is_file()
    checkpoint = _json(result.workspace / "execution/checkpoint_manifest.json")
    assert "DS10" in checkpoint["completed_nodes"]


def test_projection_is_deterministic_across_runs(tmp_path: Path) -> None:
    source = tmp_path / "stable.txt"
    source.write_text("stable\n", encoding="utf-8")
    request = request_for(source)
    first = _json(_ir_path(run_ir(request, tmp_path / "out1").workspace))
    second = _json(_ir_path(run_ir(request, tmp_path / "out2").workspace))
    assert [unit["unit_id"] for unit in first["units"]] == [
        unit["unit_id"] for unit in second["units"]
    ]
    assert first["header"]["content_hash"] == second["header"]["content_hash"]


def test_ds10_rejects_altered_native_contract(tmp_path: Path) -> None:
    source = tmp_path / "altered.txt"
    source.write_text("before", encoding="utf-8")
    request = request_for(source)
    native = run_native(request, tmp_path / "out")
    profile_path = _native_dir(native.workspace) / "profile.json"
    profile = _json(profile_path)
    profile["lines"][0]["text"] = "after"
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    with pytest.raises(StageFailure, match="Hash"):
        run_ir(request, tmp_path / "unused", resume_from=native.workspace)


def test_pure_projection_does_not_mutate_inputs(tmp_path: Path) -> None:
    source = tmp_path / "pure.txt"
    source.write_text("pure", encoding="utf-8")
    native_result = run_native(request_for(source), tmp_path / "out")
    directory = _native_dir(native_result.workspace)
    values = [
        _json(directory / name)
        for name in (
            "native_document.json",
            "profile.json",
            "styles.json",
            "relationships.json",
            "annotations.json",
            "resources.json",
        )
    ]
    snapshots = copy.deepcopy(values)
    body, _ = project_document(*values)
    validate_ir_invariants(body)
    assert values == snapshots


def test_ir_invariants_reject_orphan_parent() -> None:
    with pytest.raises(ProjectionError, match="Parent IR orphelin"):
        validate_ir_invariants(
            {
                "document_id": "document_example",
                "root_unit_ids": ["ir_root"],
                "units": [
                    {
                        "unit_id": "ir_root",
                        "kind": "document",
                        "parent_id": None,
                        "ordinal": 0,
                        "origin": "synthetic",
                        "source_native_ids": [],
                        "text": None,
                        "protected": False,
                        "style_refs": [],
                        "resource_refs": [],
                        "technical_properties": [],
                    },
                    {
                        "unit_id": "ir_child",
                        "kind": "text_line",
                        "parent_id": "missing",
                        "ordinal": 0,
                        "origin": "native_projection",
                        "source_native_ids": ["line_1"],
                        "text": "x",
                        "protected": False,
                        "style_refs": [],
                        "resource_refs": [],
                        "technical_properties": [],
                    },
                ],
            }
        )


def test_fixed_layout_projects_pages_and_annotations(tmp_path: Path) -> None:
    from ds07_ds09.test_native_additional_formats import _minimal_pdf

    source = tmp_path / "page.pdf"
    source.write_bytes(_minimal_pdf())
    result = run_ir(request_for(source), tmp_path / "out")
    ir = _json(_ir_path(result.workspace))
    page = next(unit for unit in ir["units"] if unit["kind"] == "fixed_page")
    properties = {item["name"]: item["value"] for item in page["technical_properties"]}
    assert properties["page.width"] == 595.0
    assert properties["page.height"] == 842.0
    assert any(unit["kind"] == "annotation_text" for unit in ir["units"])


def test_raster_projection_preserves_multiframe_policy(tmp_path: Path) -> None:
    source = tmp_path / "animated.gif"
    source.write_bytes(
        b"GIF89a" + b"\x02\x00\x03\x00" + b"\x00\x00\x00" + b"\x2c" + b"x" * 8 + b"\x2c" + b"y" * 8
    )
    result = run_ir(request_for(source), tmp_path / "out")
    ir = _json(_ir_path(result.workspace))
    frames = [unit for unit in ir["units"] if unit["kind"] == "image_frame"]
    assert len(frames) == 2
    assert all(unit["protected"] is True for unit in frames)
    first_properties = {item["name"]: item["value"] for item in frames[0]["technical_properties"]}
    assert first_properties["frame.surface_policy"] == "single_surface"


def test_legacy_ole_projection_is_explicitly_protected(tmp_path: Path) -> None:
    from ds07_ds09.test_native_additional_formats import _minimal_cfb

    source = tmp_path / "legacy.doc"
    source.write_bytes(_minimal_cfb())
    result = run_ir(request_for(source), tmp_path / "out")
    ir = _json(_ir_path(result.workspace))
    streams = [unit for unit in ir["units"] if unit["kind"] == "ole_stream"]
    assert streams
    assert all(unit["protected"] is True for unit in streams)
    assert ir["header"]["status"] == "review"

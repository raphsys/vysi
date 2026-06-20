from __future__ import annotations

import hashlib
import json
import struct
import zlib
from pathlib import Path

import pytest
from ds00_ds06.helpers import request_for
from ds07_ds09.test_native_additional_formats import _minimal_cfb, _minimal_pdf
from ds07_ds09.test_native_pipeline import _two_frame_tiff
from helpers import CONTENT_TYPES, make_docx, make_pptx, make_xlsx

from vysi.document_source.execution.coordinator import (
    run_ir,
    run_mapping,
    run_quality,
    run_rendering,
    run_validation,
)
from vysi.document_source.execution.errors import StageFailure


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _document_dir(root: Path, name: str) -> Path:
    return next((root / name).glob("document_*"))


def _render_request(path: Path, mode: str = "on_demand") -> dict:
    return request_for(
        path,
        rendering_policy={"mode": mode, "profiles": ["source_reference"]},
    )


def _png(path: Path, width: int = 3, height: int = 2) -> None:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    raw = b"".join(b"\x00" + b"\xff\x00\x00" * width for _ in range(height))
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(payload)


def test_mode_none_is_explicitly_completed_without_render_catalogs(tmp_path: Path) -> None:
    source = tmp_path / "none.txt"
    source.write_text("none\n", encoding="utf-8")
    result = run_validation(request_for(source), tmp_path / "out")
    assert "DS11" in result.completed_nodes
    assert (result.workspace / "RENDERING_COMPLETE").is_file()
    assert not (result.workspace / "rendered").exists()
    coverage = _json(_document_dir(result.workspace, "quality") / "feature_coverage_report.json")
    assert coverage["axis_scores"]["visual"] is None


def test_text_preview_is_hash_checked_and_integrated_through_ds14(tmp_path: Path) -> None:
    source = tmp_path / "preview.txt"
    source.write_text("alpha\nbeta\n", encoding="utf-8")
    result = run_validation(_render_request(source), tmp_path / "out")
    rendered_dir = _document_dir(result.workspace, "rendered")
    rendered = _json(rendered_dir / "rendered_view_catalog.json")
    geometry = _json(rendered_dir / "geometry_catalog.json")
    assets = _json(rendered_dir / "derived_asset_catalog.json")
    mapping = _json(
        _document_dir(result.workspace, "mapping") / "representation_mapping_catalog.json"
    )
    coverage = _json(_document_dir(result.workspace, "quality") / "feature_coverage_report.json")
    validation = _json(result.workspace / "validation/validation_report.json")

    assert rendered["views"][0]["status"] == "partial"
    assert rendered["surfaces"][0]["fidelity"] == "approximate"
    assert geometry["geometries"][0]["method"] == "vysi_builtin_svg_canvas"
    stored = assets["assets"][0]["stored_ref"]
    asset_path = result.workspace / stored["path"]
    assert asset_path.is_file()
    assert asset_path.stat().st_size == stored["size_bytes"]
    assert hashlib.sha256(asset_path.read_bytes()).hexdigest() == stored["sha256"]
    assert any(
        edge["source_layer"] == "native" and edge["target_layer"] == "rendered"
        for edge in mapping["mappings"]
    )
    assert any(
        edge["source_layer"] == "technical_ir" and edge["target_layer"] == "rendered"
        for edge in mapping["mappings"]
    )
    assert coverage["axis_scores"]["visual"] == 0.5
    assert validation["package_status"] == "review"
    assert validation["commit_eligible"] is True
    assert not (result.workspace / "COMMITTED").exists()


@pytest.mark.parametrize("kind", ["docx", "xlsx", "pptx"])
def test_application_profiles_publish_truthful_technical_previews(
    tmp_path: Path, kind: str
) -> None:
    source = tmp_path / f"sample.{kind}"
    {"docx": make_docx, "xlsx": make_xlsx, "pptx": make_pptx}[kind](source)
    result = run_quality(_render_request(source), tmp_path / "out")
    rendered = _json(_document_dir(result.workspace, "rendered") / "rendered_view_catalog.json")
    assert rendered["views"][0]["status"] == "partial"
    assert rendered["views"][0]["warnings"]
    assert rendered["surfaces"]
    assert all(item["fidelity"] == "approximate" for item in rendered["surfaces"])


def test_raster_passthrough_is_exact(tmp_path: Path) -> None:
    source = tmp_path / "sample.png"
    _png(source)
    result = run_quality(_render_request(source), tmp_path / "out")
    rendered_dir = _document_dir(result.workspace, "rendered")
    rendered = _json(rendered_dir / "rendered_view_catalog.json")
    assets = _json(rendered_dir / "derived_asset_catalog.json")
    coverage = _json(_document_dir(result.workspace, "quality") / "feature_coverage_report.json")
    assert rendered["views"][0]["status"] == "partial"
    assert rendered["views"][0]["measurement_basis"] == "binary_passthrough"
    assert rendered["surfaces"][0]["fidelity"] == "not_assessed"
    stored = assets["assets"][0]["stored_ref"]
    assert (
        hashlib.sha256((result.workspace / stored["path"]).read_bytes()).hexdigest()
        == hashlib.sha256(source.read_bytes()).hexdigest()
    )
    assert coverage["axis_scores"]["visual"] is None


def test_required_unsupported_legacy_rendering_fails_at_ds11(tmp_path: Path) -> None:
    source = tmp_path / "legacy.doc"
    source.write_bytes(_minimal_cfb())
    with pytest.raises(StageFailure) as caught:
        run_rendering(_render_request(source, "required"), tmp_path / "out")
    assert caught.value.stage == "DS11"
    assert caught.value.code in {"DS-RND-002", "DS-DEC-002"}


def test_rendering_resumes_from_ir_checkpoint(tmp_path: Path) -> None:
    source = tmp_path / "resume.txt"
    source.write_text("resume\n", encoding="utf-8")
    request = _render_request(source)
    ir = run_ir(request, tmp_path / "out")
    rendered = run_rendering(request, tmp_path / "unused", resume_from=ir.workspace)
    assert rendered.workspace == ir.workspace
    assert "DS11" in rendered.completed_nodes
    assert (rendered.workspace / "RENDERING_COMPLETE").is_file()


def test_tampered_rendered_asset_is_rejected_before_mapping(tmp_path: Path) -> None:
    source = tmp_path / "tamper.txt"
    source.write_text("tamper\n", encoding="utf-8")
    request = _render_request(source)
    rendered = run_rendering(request, tmp_path / "out")
    catalog = _json(_document_dir(rendered.workspace, "rendered") / "derived_asset_catalog.json")
    asset_path = rendered.workspace / catalog["assets"][0]["stored_ref"]["path"]
    asset_path.write_bytes(asset_path.read_bytes() + b"tampered")
    with pytest.raises(StageFailure, match="Hash"):
        run_mapping(request, tmp_path / "unused", resume_from=rendered.workspace)


def test_rendering_identifiers_and_asset_bytes_are_deterministic(tmp_path: Path) -> None:
    source = tmp_path / "stable.txt"
    source.write_text("stable\n", encoding="utf-8")
    request = _render_request(source)
    first = run_rendering(request, tmp_path / "out1")
    second = run_rendering(request, tmp_path / "out2")
    first_dir = _document_dir(first.workspace, "rendered")
    second_dir = _document_dir(second.workspace, "rendered")
    first_rendered = _json(first_dir / "rendered_view_catalog.json")
    second_rendered = _json(second_dir / "rendered_view_catalog.json")
    first_assets = _json(first_dir / "derived_asset_catalog.json")
    second_assets = _json(second_dir / "derived_asset_catalog.json")
    assert first_rendered["views"][0]["view_id"] == second_rendered["views"][0]["view_id"]
    assert (
        first_rendered["surfaces"][0]["surface_id"] == second_rendered["surfaces"][0]["surface_id"]
    )
    assert first_assets["assets"][0]["asset_id"] == second_assets["assets"][0]["asset_id"]
    assert (
        first_assets["assets"][0]["stored_ref"]["sha256"]
        == second_assets["assets"][0]["stored_ref"]["sha256"]
    )


def test_preview_svg_is_xml_safe_for_control_characters() -> None:
    import xml.etree.ElementTree as ET

    from vysi.document_source.rendering_v2.svg import svg_text_page

    payload = svg_text_page(title="control", lines=["alpha\x00beta\x01gamma"])
    root = ET.fromstring(payload)
    text = "".join(root.itertext())
    assert "alpha�beta�gamma" in text


def test_rendering_enforces_temp_asset_budget(tmp_path: Path) -> None:
    source = tmp_path / "budget.txt"
    source.write_text("budget\n", encoding="utf-8")
    request = _render_request(source)
    request["resource_budget"]["max_temp_bytes"] = 10
    from vysi.document_source.contracts_v2.canonical import content_hash

    request["header"]["content_hash"] = content_hash(request)
    with pytest.raises(StageFailure) as caught:
        run_rendering(request, tmp_path / "out")
    assert caught.value.stage == "DS11"
    assert caught.value.code == "DS-LIM-001"


def test_multiple_render_profiles_remain_distinct_and_traceable(tmp_path: Path) -> None:
    source = tmp_path / "multi.png"
    _png(source)
    request = request_for(
        source,
        rendering_policy={
            "mode": "on_demand",
            "profiles": ["source_reference", "native_passthrough"],
        },
    )
    result = run_quality(request, tmp_path / "out")
    rendered = _json(_document_dir(result.workspace, "rendered") / "rendered_view_catalog.json")
    assert len(rendered["views"]) == 2
    assert {view["requested_profile"] for view in rendered["views"]} == {
        "source_reference",
        "native_passthrough",
    }
    assert all(view["view_kind"] == "native_passthrough" for view in rendered["views"])
    assert len({surface["surface_id"] for surface in rendered["surfaces"]}) == 2


def test_required_technical_preview_is_present_but_remains_review(tmp_path: Path) -> None:
    source = tmp_path / "required.txt"
    source.write_text("required preview\n", encoding="utf-8")
    result = run_validation(_render_request(source, "required"), tmp_path / "out")
    rendered = _json(_document_dir(result.workspace, "rendered") / "rendered_view_catalog.json")
    report = _json(result.workspace / "validation/validation_report.json")
    assert rendered["views"][0]["status"] == "partial"
    assert rendered["surfaces"][0]["fidelity"] == "approximate"
    assert report["package_status"] == "review"
    assert report["commit_eligible"] is True


def test_on_demand_unsupported_renderer_is_auditable_through_ds14(tmp_path: Path) -> None:
    source = tmp_path / "legacy.doc"
    source.write_bytes(_minimal_cfb())
    result = run_validation(_render_request(source, "on_demand"), tmp_path / "out")
    rendered = _json(_document_dir(result.workspace, "rendered") / "rendered_view_catalog.json")
    report = _json(result.workspace / "validation/validation_report.json")
    assert rendered["views"][0]["status"] == "unsupported"
    assert rendered["surfaces"] == []
    assert report["package_status"] == "review"
    assert report["commit_eligible"] is True


def test_checkpoint_markers_require_ds11_completion(tmp_path: Path) -> None:
    from vysi.document_source.contracts_v2.canonical import content_hash
    from vysi.document_source.execution.preflight_validation import validate_preflight

    source = tmp_path / "marker.txt"
    source.write_text("marker\n", encoding="utf-8")
    result = run_mapping(request_for(source), tmp_path / "out")
    checkpoint_path = result.workspace / "execution/checkpoint_manifest.json"
    checkpoint = _json(checkpoint_path)
    checkpoint["completed_nodes"].remove("DS11")
    checkpoint["header"]["content_hash"] = "0" * 64
    checkpoint["header"]["content_hash"] = content_hash(checkpoint)
    checkpoint_path.write_text(json.dumps(checkpoint, indent=2, sort_keys=True) + "\n")
    findings = validate_preflight(result.workspace)
    assert any(f.path == "RENDERING_COMPLETE" for f in findings)
    assert any(f.path == "MAPPING_COMPLETE" for f in findings)


def test_cli_accepts_multiple_render_profiles() -> None:
    from vysi.document_source.cli import build_parser

    args = build_parser().parse_args(
        [
            "render",
            "--source",
            "/tmp/source.png",
            "--output",
            "/tmp/output",
            "--render-mode",
            "on_demand",
            "--render-profile",
            "source_reference",
            "--render-profile",
            "native_passthrough",
        ]
    )
    assert args.render_profiles == ["source_reference", "native_passthrough"]


def test_renderer_registry_selects_highest_priority_deterministically() -> None:
    from dataclasses import dataclass

    from vysi.document_source.rendering_v2 import RendererCapability, select_renderer

    @dataclass(frozen=True)
    class Candidate:
        renderer_id: str
        renderer_version: str
        priority: int

        def capability(self, profile_kind: str, requested_profile: str) -> RendererCapability:
            assert profile_kind == "plain_text"
            assert requested_profile == "source_reference"
            return RendererCapability(True, self.priority)

        def render(self, **kwargs: object) -> object:
            raise AssertionError("La sélection ne doit pas déclencher le rendu")

    low = Candidate("z-low", "1", 10)
    high_b = Candidate("b-high", "1", 100)
    high_a = Candidate("a-high", "1", 100)
    selected = select_renderer(
        (low, high_b, high_a),
        profile_kind="plain_text",
        requested_profile="source_reference",
    )
    assert selected.renderer_id == "a-high"


def test_technical_preview_is_explicitly_unsupported_for_intrinsic_raster(
    tmp_path: Path,
) -> None:
    source = tmp_path / "intrinsic.png"
    _png(source)
    request = request_for(
        source,
        rendering_policy={"mode": "on_demand", "profiles": ["technical_preview"]},
    )
    result = run_validation(request, tmp_path / "out")
    rendered = _json(_document_dir(result.workspace, "rendered") / "rendered_view_catalog.json")
    report = _json(result.workspace / "validation/validation_report.json")
    assert rendered["views"][0]["view_kind"] == "unsupported"
    assert rendered["views"][0]["status"] == "unsupported"
    assert rendered["surfaces"] == []
    assert report["package_status"] == "review"
    assert report["commit_eligible"] is True


def test_duplicate_passthrough_profiles_count_unique_asset_bytes_once(tmp_path: Path) -> None:
    source = tmp_path / "deduplicated.png"
    _png(source, width=2, height=2)
    request = request_for(
        source,
        rendering_policy={
            "mode": "on_demand",
            "profiles": ["source_reference", "native_passthrough"],
        },
    )
    request["resource_budget"]["max_temp_bytes"] = source.stat().st_size
    from vysi.document_source.contracts_v2.canonical import content_hash

    request["header"]["content_hash"] = content_hash(request)
    result = run_rendering(request, tmp_path / "out")
    assets = _json(_document_dir(result.workspace, "rendered") / "derived_asset_catalog.json")
    rendered = _json(_document_dir(result.workspace, "rendered") / "rendered_view_catalog.json")
    assert len(assets["assets"]) == 1
    assert len(rendered["views"]) == 2
    assert {ref for surface in rendered["surfaces"] for ref in surface["asset_refs"]} == {
        assets["assets"][0]["asset_id"]
    }


def test_failed_reference_publication_removes_promoted_ds11_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import vysi.document_source.subunits.ds11_rendering as ds11

    source = tmp_path / "atomic.txt"
    source.write_text("atomic publication\n", encoding="utf-8")

    def fail_reference(*args: object, **kwargs: object) -> dict[str, str]:
        raise RuntimeError("injected reference failure")

    monkeypatch.setattr(ds11, "contract_reference", fail_reference)
    output = tmp_path / "out"
    with pytest.raises(StageFailure) as caught:
        run_rendering(_render_request(source), output)
    assert caught.value.stage == "DS11"
    workspaces = list(output.glob("preflight-*"))
    assert len(workspaces) == 1
    rendered_root = workspaces[0] / "rendered"
    assert not rendered_root.exists() or not any(rendered_root.iterdir())


def test_pdf_source_reference_is_exact_streaming_passthrough(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(_minimal_pdf())
    result = run_quality(_render_request(source), tmp_path / "out")
    rendered_dir = _document_dir(result.workspace, "rendered")
    rendered = _json(rendered_dir / "rendered_view_catalog.json")
    assets = _json(rendered_dir / "derived_asset_catalog.json")
    stored = assets["assets"][0]["stored_ref"]
    materialized = result.workspace / stored["path"]
    assert materialized.read_bytes() == source.read_bytes()
    assert rendered["views"][0]["view_kind"] == "native_passthrough"
    assert rendered["views"][0]["status"] == "partial"
    assert rendered["views"][0]["measurement_basis"] == "binary_passthrough"
    assert rendered["surfaces"][0]["fidelity"] == "not_assessed"
    assert rendered["surfaces"][0]["rotation"] == 90
    quality = _json(_document_dir(result.workspace, "quality") / "feature_coverage_report.json")
    assert quality["axis_scores"]["visual"] is None


def test_multiframe_tiff_is_preserved_as_one_asset_with_partial_surfaces(tmp_path: Path) -> None:
    source = tmp_path / "pages.tiff"
    source.write_bytes(_two_frame_tiff())
    result = run_quality(_render_request(source), tmp_path / "out")
    rendered_dir = _document_dir(result.workspace, "rendered")
    rendered = _json(rendered_dir / "rendered_view_catalog.json")
    assets = _json(rendered_dir / "derived_asset_catalog.json")
    assert len(assets["assets"]) == 1
    assert len(rendered["surfaces"]) == 2
    assert {item["status"] for item in rendered["surfaces"]} == {"partial"}
    assert {item["fidelity"] for item in rendered["surfaces"]} == {"not_assessed"}
    assert len({ref for item in rendered["surfaces"] for ref in item["asset_refs"]}) == 1
    assert "multiframe_source_preserved_as_single_container_asset" in rendered["views"][0][
        "warnings"
    ]


def test_ds11_cancellation_from_ds10_then_resume(tmp_path: Path) -> None:
    source = tmp_path / "resume-render.txt"
    source.write_text("resume DS11\n", encoding="utf-8")
    request = _render_request(source)
    ir_result = run_ir(request, tmp_path / "out")
    cancel = tmp_path / "CANCEL"
    cancel.write_text("cancel", encoding="utf-8")
    with pytest.raises(StageFailure) as caught:
        run_rendering(
            request,
            tmp_path / "unused",
            resume_from=ir_result.workspace,
            cancel_file=cancel,
        )
    assert caught.value.code == "DS-RUN-003"
    assert not (ir_result.workspace / "RENDERING_COMPLETE").exists()
    cancel.unlink()
    completed = run_rendering(request, tmp_path / "unused", resume_from=ir_result.workspace)
    assert completed.workspace == ir_result.workspace
    assert (completed.workspace / "RENDERING_COMPLETE").is_file()


def test_cross_catalog_validator_rejects_orphan_asset_reference(tmp_path: Path) -> None:
    from copy import deepcopy

    from vysi.document_source.rendering_v2 import validate_rendering_invariants

    source = tmp_path / "orphan.txt"
    source.write_text("orphan\n", encoding="utf-8")
    result = run_rendering(_render_request(source), tmp_path / "out")
    rendered_dir = _document_dir(result.workspace, "rendered")
    rendered = _json(rendered_dir / "rendered_view_catalog.json")
    geometry = _json(rendered_dir / "geometry_catalog.json")
    assets = _json(rendered_dir / "derived_asset_catalog.json")
    corrupted = deepcopy(rendered)
    corrupted["surfaces"][0]["asset_refs"] = ["asset_missing_reference"]
    with pytest.raises(ValueError, match="orpheline|absent|inconnu"):
        validate_rendering_invariants(corrupted, geometry, assets)


def test_long_text_is_wrapped_paginated_and_geometrically_visible(tmp_path: Path) -> None:
    source = tmp_path / "long.txt"
    source.write_text("A" * 12000 + "\nsecond line\n", encoding="utf-8")
    result = run_quality(_render_request(source), tmp_path / "out")
    rendered_dir = _document_dir(result.workspace, "rendered")
    rendered = _json(rendered_dir / "rendered_view_catalog.json")
    geometry = _json(rendered_dir / "geometry_catalog.json")
    coverage = _json(_document_dir(result.workspace, "quality") / "feature_coverage_report.json")

    assert len(rendered["surfaces"]) >= 2
    visible_refs = {
        ref for surface in rendered["surfaces"] for ref in surface["native_unit_refs"]
    }
    serialized_refs = {
        ref
        for surface in rendered["surfaces"]
        for ref in surface["serialized_native_unit_refs"]
    }
    assert visible_refs == serialized_refs
    assert all(not surface["omitted_native_unit_refs"] for surface in rendered["surfaces"])
    element_refs = {
        ref
        for item in geometry["geometries"]
        if item["visibility"] in {"fully_visible", "partially_clipped"}
        for ref in item["native_unit_refs"]
    }
    assert visible_refs <= element_refs
    visibility = next(
        item
        for item in coverage["items"]
        if item["feature"] == "rendered_native_visibility"
    )
    assert visibility["required"] == visibility["rendered"]
    assert coverage["axis_scores"]["visual"] == 0.5


def _large_xlsx(path: Path, rows: int = 40, cols: int = 20) -> None:
    import zipfile

    def col_name(index: int) -> str:
        value = ""
        while index:
            index, remainder = divmod(index - 1, 26)
            value = chr(65 + remainder) + value
        return value

    workbook = """<workbook xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main' xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships'><sheets><sheet name='Large' sheetId='1' r:id='rId1'/></sheets></workbook>"""
    rels = """<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'><Relationship Id='rId1' Type='worksheet' Target='worksheets/sheet1.xml'/></Relationships>"""
    rows_xml: list[str] = []
    for row in range(1, rows + 1):
        cells = []
        for col in range(1, cols + 1):
            address = f"{col_name(col)}{row}"
            value = f"value-{row}-{col}-" + ("X" * 80 if row == 1 and col == 1 else "")
            cells.append(f"<c r='{address}' t='inlineStr'><is><t>{value}</t></is></c>")
        rows_xml.append(f"<row r='{row}'>{''.join(cells)}</row>")
    sheet = (
        "<worksheet xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'>"
        f"<sheetData>{''.join(rows_xml)}</sheetData></worksheet>"
    )
    types = CONTENT_TYPES.format(
        items="<Override PartName='/xl/workbook.xml' ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml'/><Override PartName='/xl/worksheets/sheet1.xml' ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml'/>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", types)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", rels)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)


def test_large_spreadsheet_is_tiled_without_false_surface_coverage(tmp_path: Path) -> None:
    source = tmp_path / "large.xlsx"
    _large_xlsx(source)
    result = run_quality(_render_request(source), tmp_path / "out")
    rendered = _json(_document_dir(result.workspace, "rendered") / "rendered_view_catalog.json")
    geometry = _json(_document_dir(result.workspace, "rendered") / "geometry_catalog.json")
    profile = _json(_document_dir(result.workspace, "native") / "profile.json")
    coverage = _json(_document_dir(result.workspace, "quality") / "feature_coverage_report.json")

    assert len(rendered["surfaces"]) >= 4
    cell_ids = {str(item["cell_id"]) for item in profile["cells"]}
    visible = {ref for surface in rendered["surfaces"] for ref in surface["native_unit_refs"]}
    assert cell_ids <= visible
    assert any(surface["clipped_native_unit_refs"] for surface in rendered["surfaces"])
    geometric = {
        ref
        for item in geometry["geometries"]
        if item["role"] == "cell"
        for ref in item["native_unit_refs"]
    }
    assert cell_ids <= geometric
    visibility = next(
        item
        for item in coverage["items"]
        if item["feature"] == "rendered_native_visibility"
    )
    assert visibility["omitted"] == 0
    assert visibility["approximated"] >= 1
    assert 0 < coverage["axis_scores"]["visual"] < 0.5


def _pptx_with_non_text_shape(path: Path) -> None:
    import zipfile

    presentation = """<p:presentation xmlns:p='http://schemas.openxmlformats.org/presentationml/2006/main' xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships'><p:sldIdLst><p:sldId id='256' r:id='rId1'/></p:sldIdLst></p:presentation>"""
    rels = """<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'><Relationship Id='rId1' Type='slide' Target='slides/slide1.xml'/></Relationships>"""
    slide = """<p:sld xmlns:p='http://schemas.openxmlformats.org/presentationml/2006/main' xmlns:a='http://schemas.openxmlformats.org/drawingml/2006/main'><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>Visible title</a:t></a:r></a:p></p:txBody></p:sp><p:pic/><p:graphicFrame/></p:spTree></p:cSld></p:sld>"""
    types = CONTENT_TYPES.format(
        items="<Override PartName='/ppt/presentation.xml' ContentType='application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml'/><Override PartName='/ppt/slides/slide1.xml' ContentType='application/vnd.openxmlformats-officedocument.presentationml.slide+xml'/>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", types)
        archive.writestr("ppt/presentation.xml", presentation)
        archive.writestr("ppt/_rels/presentation.xml.rels", rels)
        archive.writestr("ppt/slides/slide1.xml", slide)


def test_presentation_non_text_shapes_receive_visible_placeholders(tmp_path: Path) -> None:
    source = tmp_path / "shapes.pptx"
    _pptx_with_non_text_shape(source)
    result = run_quality(_render_request(source), tmp_path / "out")
    rendered = _json(_document_dir(result.workspace, "rendered") / "rendered_view_catalog.json")
    geometry = _json(_document_dir(result.workspace, "rendered") / "geometry_catalog.json")
    profile = _json(_document_dir(result.workspace, "native") / "profile.json")

    shape_ids = {str(item["shape_id"]) for item in profile["shapes"]}
    visible = {ref for surface in rendered["surfaces"] for ref in surface["native_unit_refs"]}
    assert shape_ids <= visible
    placeholder_refs = {
        ref
        for item in geometry["geometries"]
        if item["role"] == "shape_placeholder"
        for ref in item["native_unit_refs"]
    }
    assert len(placeholder_refs) == 2


def test_passthrough_preservation_does_not_claim_visual_fidelity(tmp_path: Path) -> None:
    pdf = tmp_path / "preserved.pdf"
    pdf.write_bytes(_minimal_pdf())
    result = run_quality(_render_request(pdf), tmp_path / "out")
    rendered = _json(_document_dir(result.workspace, "rendered") / "rendered_view_catalog.json")
    coverage = _json(_document_dir(result.workspace, "quality") / "feature_coverage_report.json")
    assert rendered["views"][0]["measurement_basis"] == "binary_passthrough"
    assert rendered["views"][0]["visibility_summary"]["visual_fidelity_assessed"] is False
    assert all(surface["fidelity"] == "not_assessed" for surface in rendered["surfaces"])
    assert coverage["axis_scores"]["binary"] == 1.0
    assert coverage["axis_scores"]["visual"] is None


def test_rendering_invariants_reject_visible_reference_without_geometry(tmp_path: Path) -> None:
    from copy import deepcopy

    from vysi.document_source.rendering_v2 import validate_rendering_invariants

    source = tmp_path / "visibility.txt"
    source.write_text("visible\n", encoding="utf-8")
    result = run_rendering(_render_request(source), tmp_path / "out")
    rendered_dir = _document_dir(result.workspace, "rendered")
    rendered = _json(rendered_dir / "rendered_view_catalog.json")
    geometry = _json(rendered_dir / "geometry_catalog.json")
    assets = _json(rendered_dir / "derived_asset_catalog.json")
    corrupted = deepcopy(geometry)
    corrupted["geometries"] = [
        item for item in corrupted["geometries"] if not item["native_unit_refs"]
    ]
    with pytest.raises(ValueError, match="sans géométrie"):
        validate_rendering_invariants(rendered, corrupted, assets)

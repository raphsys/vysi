from __future__ import annotations

import json
import struct
from pathlib import Path

from ds00_ds06.helpers import request_for
from helpers import make_docx, make_pptx, make_xlsx

from vysi.document_source.execution.coordinator import run_native, run_preflight
from vysi.document_source.execution.preflight_validation import validate_preflight


def _document_dir(workspace: Path) -> Path:
    return next(
        path
        for path in (workspace / "native").iterdir()
        if path.is_dir() and path.name.startswith("document_")
    )


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_text_materializes_contracts_without_final_commit(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("alpha\nbeta\n", encoding="utf-8")
    result = run_native(request_for(source), tmp_path / "out")
    assert (result.workspace / "PREFLIGHT_COMPLETE").is_file()
    assert (result.workspace / "NATIVE_COMPLETE").is_file()
    assert not (result.workspace / "COMMITTED").exists()
    profile = _json(_document_dir(result.workspace) / "profile.json")
    assert profile["header"]["schema_version"] == "2.2.0"
    assert profile["profile_kind"] == "plain_text"
    assert [line["text"] for line in profile["lines"]] == ["alpha", "beta"]
    assert validate_preflight(result.workspace) == ()


def test_docx_container_and_native_hierarchy(tmp_path: Path) -> None:
    source = tmp_path / "sample.docx"
    make_docx(source)
    result = run_native(request_for(source), tmp_path / "out")
    container = _json(next((result.workspace / "manifests/container").glob("*.json")))
    assert {part["path"] for part in container["parts"]} >= {
        "[Content_Types].xml",
        "word/document.xml",
        "word/styles.xml",
    }
    profile = _json(_document_dir(result.workspace) / "profile.json")
    assert profile["profile_kind"] == "wordprocessing"
    assert {block["kind"] for block in profile["blocks"]} >= {
        "paragraph",
        "run",
        "table",
        "row",
        "cell",
    }


def test_xlsx_formula_is_preserved_and_never_recalculated(tmp_path: Path) -> None:
    source = tmp_path / "sample.xlsx"
    make_xlsx(source)
    result = run_native(request_for(source), tmp_path / "out")
    profile = _json(_document_dir(result.workspace) / "profile.json")
    model = profile["calculation_model"]
    assert model["recalculated"] is False
    assert model["formulas"][0]["source"] == "SUM(B2:B3)"
    assert model["formulas"][0]["dependency_refs"] == ["B2", "B3"]


def test_pptx_slide_and_shape_are_native_units(tmp_path: Path) -> None:
    source = tmp_path / "sample.pptx"
    make_pptx(source)
    result = run_native(request_for(source), tmp_path / "out")
    profile = _json(_document_dir(result.workspace) / "profile.json")
    assert len(profile["slides"]) == 1
    assert any(shape["text"] == "Titre" for shape in profile["shapes"])


def test_preflight_checkpoint_can_resume_through_ds09(tmp_path: Path) -> None:
    source = tmp_path / "resume.txt"
    source.write_text("resume", encoding="utf-8")
    request = request_for(source)
    preflight = run_preflight(request, tmp_path / "out")
    assert (preflight.workspace / "PREFLIGHT_COMPLETE").is_file()
    assert not (preflight.workspace / "NATIVE_COMPLETE").exists()
    native = run_native(request, tmp_path / "unused", resume_from=preflight.workspace)
    assert native.workspace == preflight.workspace
    assert (native.workspace / "NATIVE_COMPLETE").is_file()
    checkpoint = _json(native.workspace / "execution/checkpoint_manifest.json")
    assert {"DS07", "DS08", "DS09"}.issubset(checkpoint["completed_nodes"])


def test_multiframe_gif_remains_one_visual_document_with_multiple_frames(tmp_path: Path) -> None:
    source = tmp_path / "animated.gif"
    # Header and logical screen descriptor followed by two image separators. The minimal
    # native reader inventories frame semantics without executing a decoder.
    source.write_bytes(
        b"GIF89a"
        + struct.pack("<HH", 2, 3)
        + b"\x00\x00\x00"
        + b"\x2c"
        + b"x" * 8
        + b"\x2c"
        + b"y" * 8
    )
    result = run_native(request_for(source), tmp_path / "out")
    profile = _json(_document_dir(result.workspace) / "profile.json")
    assert profile["profile_kind"] == "raster"
    assert profile["animated"] is True
    assert profile["document_surface_policy"] == "single_surface"
    assert len(profile["frames"]) == 2


def _two_frame_tiff() -> bytes:
    # Little-endian TIFF with two IFDs, each declaring width=2 and height=3.
    header = b"II*\x00" + struct.pack("<I", 8)
    first_offset = 8
    first_size = 2 + 2 * 12 + 4
    second_offset = first_offset + first_size

    def ifd(next_offset: int) -> bytes:
        return (
            struct.pack("<H", 2)
            + struct.pack("<HHII", 256, 4, 1, 2)
            + struct.pack("<HHII", 257, 4, 1, 3)
            + struct.pack("<I", next_offset)
        )

    return header + ifd(second_offset) + ifd(0)


def test_multiframe_tiff_maps_one_surface_per_frame(tmp_path: Path) -> None:
    source = tmp_path / "pages.tiff"
    source.write_bytes(_two_frame_tiff())
    result = run_native(request_for(source), tmp_path / "out")
    profile = _json(_document_dir(result.workspace) / "profile.json")
    assert len(profile["frames"]) == 2
    assert profile["document_surface_policy"] == "one_surface_per_frame"

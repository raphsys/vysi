from __future__ import annotations

import json
import struct
from pathlib import Path

from ds00_ds06.helpers import request_for

from vysi.document_source.execution.coordinator import run_native
from vysi.document_source.execution.preflight_validation import validate_preflight

FREESECT = 0xFFFFFFFF
ENDOFCHAIN = 0xFFFFFFFE
FATSECT = 0xFFFFFFFD
OLE_MAGIC = bytes.fromhex("D0CF11E0A1B11AE1")


def _document_dir(workspace: Path) -> Path:
    return next(
        path
        for path in (workspace / "native").iterdir()
        if path.is_dir() and path.name.startswith("document_")
    )


def _directory_entry(
    name: str,
    object_type: int,
    *,
    child: int = FREESECT,
    start_sector: int = ENDOFCHAIN,
    size: int = 0,
) -> bytes:
    raw = bytearray(128)
    encoded = (name + "\x00").encode("utf-16le")
    raw[: min(len(encoded), 64)] = encoded[:64]
    struct.pack_into("<H", raw, 64, min(len(encoded), 64))
    raw[66] = object_type
    raw[67] = 1
    struct.pack_into("<I", raw, 68, FREESECT)
    struct.pack_into("<I", raw, 72, FREESECT)
    struct.pack_into("<I", raw, 76, child)
    struct.pack_into("<I", raw, 116, start_sector)
    struct.pack_into("<Q", raw, 120, size)
    return bytes(raw)


def _minimal_cfb() -> bytes:
    sector_size = 512
    header = bytearray(sector_size)
    header[:8] = OLE_MAGIC
    struct.pack_into("<H", header, 0x18, 0x003E)
    struct.pack_into("<H", header, 0x1A, 3)
    struct.pack_into("<H", header, 0x1C, 0xFFFE)
    struct.pack_into("<H", header, 0x1E, 9)
    struct.pack_into("<H", header, 0x20, 6)
    struct.pack_into("<I", header, 0x28, 0)
    struct.pack_into("<I", header, 0x2C, 1)
    struct.pack_into("<I", header, 0x30, 0)
    struct.pack_into("<I", header, 0x34, 0)
    struct.pack_into("<I", header, 0x38, 4096)
    struct.pack_into("<I", header, 0x3C, ENDOFCHAIN)
    struct.pack_into("<I", header, 0x40, 0)
    struct.pack_into("<I", header, 0x44, ENDOFCHAIN)
    struct.pack_into("<I", header, 0x48, 0)
    difat = [1] + [FREESECT] * 108
    struct.pack_into("<109I", header, 0x4C, *difat)

    directory = bytearray(sector_size)
    directory[0:128] = _directory_entry("Root Entry", 5, child=1)
    directory[128:256] = _directory_entry(
        "WordDocument",
        2,
        start_sector=2,
        size=4096,
    )

    fat = [FREESECT] * (sector_size // 4)
    fat[0] = ENDOFCHAIN
    fat[1] = FATSECT
    for sector in range(2, 9):
        fat[sector] = sector + 1
    fat[9] = ENDOFCHAIN
    fat_sector = struct.pack("<128I", *fat)
    payload = b"Vysi legacy OLE test".ljust(4096, b"\x00")
    return bytes(header) + bytes(directory) + fat_sector + payload


def _minimal_pdf() -> bytes:
    return (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Count 1 /Kids [3 0 R] >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Rotate 90 "
        b"/Annots [4 0 R] >> endobj\n"
        b"4 0 obj << /Type /Annot /Subtype /Text >> endobj\n"
        b"xref\n0 5\n0000000000 65535 f \n"
        b"trailer << /Root 1 0 R /Size 5 >>\n"
        b"startxref\n0\n%%EOF\n"
    )


def test_legacy_ole_inventory_is_preserved_as_partial_native_profile(tmp_path: Path) -> None:
    source = tmp_path / "legacy.doc"
    source.write_bytes(_minimal_cfb())
    result = run_native(request_for(source), tmp_path / "out")
    container = json.loads(
        next((result.workspace / "manifests/container").glob("*.json")).read_text()
    )
    stream = next(part for part in container["parts"] if part["part_kind"] == "stream")
    assert stream["path"].endswith("WordDocument")
    assert stream["size_bytes"] == 4096
    assert stream["sha256"]

    profile = json.loads((_document_dir(result.workspace) / "profile.json").read_text())
    assert profile["profile_kind"] == "legacy_ole"
    assert profile["coverage_level"] == "inventory_only"
    assert profile["semantic_format_hint"] == "doc"
    assert profile["streams"][0]["read_state"] == "preserved"
    assert validate_preflight(result.workspace) == ()


def test_pdf_fixed_layout_profile_preserves_page_geometry_and_annotation(tmp_path: Path) -> None:
    source = tmp_path / "one-page.pdf"
    source.write_bytes(_minimal_pdf())
    result = run_native(request_for(source), tmp_path / "out")
    document_dir = _document_dir(result.workspace)
    profile = json.loads((document_dir / "profile.json").read_text())
    assert profile["profile_kind"] == "fixed_layout"
    assert len(profile["pages"]) == 1
    assert profile["pages"][0]["width_pt"] == 595.0
    assert profile["pages"][0]["height_pt"] == 842.0
    assert profile["pages"][0]["rotation"] == 90
    annotations = json.loads((document_dir / "annotations.json").read_text())
    assert annotations["annotations"][0]["kind"] == "text"
    assert validate_preflight(result.workspace) == ()


def test_native_object_identities_are_stable_across_runs(tmp_path: Path) -> None:
    source = tmp_path / "stable.txt"
    source.write_text("alpha\nbeta\n", encoding="utf-8")
    first = run_native(request_for(source), tmp_path / "first")
    second = run_native(request_for(source), tmp_path / "second")

    first_profile = json.loads((_document_dir(first.workspace) / "profile.json").read_text())
    second_profile = json.loads((_document_dir(second.workspace) / "profile.json").read_text())
    assert first_profile["document_id"] == second_profile["document_id"]
    assert [line["unit_id"] for line in first_profile["lines"]] == [
        line["unit_id"] for line in second_profile["lines"]
    ]
    assert first_profile["header"]["contract_id"] == second_profile["header"]["contract_id"]
    first_run = json.loads((first.workspace / "execution/run_manifest.json").read_text())
    second_run = json.loads((second.workspace / "execution/run_manifest.json").read_text())
    assert first_run["run_id"] != second_run["run_id"]

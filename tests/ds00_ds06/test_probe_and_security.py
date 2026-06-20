from __future__ import annotations

import json
import zipfile
from pathlib import Path

from vysi.document_source.execution.coordinator import run_preflight

from .helpers import request_for


def test_unknown_binary_is_not_misclassified_as_text(tmp_path: Path) -> None:
    source = tmp_path / "unknown.txt"
    source.write_bytes(b"\x00\xff\x01\x02" * 100)
    result = run_preflight(request_for(source), tmp_path / "out")
    probe = json.loads((result.workspace / "manifests/format_probe_report.json").read_text())
    assert probe["documents"][0]["format_name"] == "unknown_binary"
    assert probe["documents"][0]["extension_mismatch"] is True


def test_extension_mismatch_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "fake.pdf"
    source.write_text("plain text", encoding="utf-8")
    result = run_preflight(request_for(source), tmp_path / "out")
    probe = json.loads((result.workspace / "manifests/format_probe_report.json").read_text())
    assert probe["documents"][0]["format_name"] == "txt"
    assert probe["documents"][0]["extension_mismatch"] is True


def test_docx_macro_is_inventoried_and_never_executed(tmp_path: Path) -> None:
    source = tmp_path / "macro.docm"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<w:document xmlns:w='w'/>")
        archive.writestr("word/vbaProject.bin", b"not executable")
    result = run_preflight(request_for(source), tmp_path / "out")
    probe = json.loads((result.workspace / "manifests/format_probe_report.json").read_text())
    security = json.loads((result.workspace / "manifests/security_clearance.json").read_text())
    assert probe["documents"][0]["format_name"] == "docx"
    assert security["active_content_execution_enabled"] is False
    assert any(item["code"] == "DS-SEC-003" for item in security["findings"])


def test_zip_traversal_is_blocked_without_extraction(tmp_path: Path) -> None:
    source = tmp_path / "unsafe.docx"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<w:document xmlns:w='w'/>")
        archive.writestr("../escape.txt", "forbidden")
    result = run_preflight(request_for(source), tmp_path / "out")
    security = json.loads((result.workspace / "manifests/security_clearance.json").read_text())
    access_path = next((result.workspace / "manifests/access").glob("*.json"))
    access = json.loads(access_path.read_text())
    assert security["decision"] == "block"
    assert access["access_state"] == "blocked"
    assert not (result.workspace.parent / "escape.txt").exists()


def test_high_compression_ratio_is_blocked_from_metadata_only(tmp_path: Path) -> None:
    source = tmp_path / "bomb.docx"
    with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", b"0" * (11 * 1024 * 1024))
    result = run_preflight(request_for(source), tmp_path / "out")
    security = json.loads((result.workspace / "manifests/security_clearance.json").read_text())
    assert security["decision"] == "block"
    assert any("compression" in item["message"].lower() for item in security["findings"])

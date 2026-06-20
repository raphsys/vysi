from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from ds00_ds06.helpers import request_for
from helpers import CONTENT_TYPES

from vysi.document_source.contracts_v2.canonical import content_hash
from vysi.document_source.execution.contracts import make_contract
from vysi.document_source.execution.coordinator import run_native, run_preflight
from vysi.document_source.execution.errors import StageFailure
from vysi.document_source.execution.preflight_validation import validate_preflight


def _document_dir(workspace: Path) -> Path:
    return next(
        path
        for path in (workspace / "native").iterdir()
        if path.is_dir() and path.name.startswith("document_")
    )


def test_macro_resource_is_catalogued_active_but_never_executed(tmp_path: Path) -> None:
    source = tmp_path / "macro.docm"
    types = CONTENT_TYPES.format(
        items="<Override PartName='/word/document.xml' ContentType='application/vnd.ms-word.document.macroEnabled.main+xml'/><Override PartName='/word/vbaProject.bin' ContentType='application/vnd.ms-office.vbaProject'/>"
    )
    document = "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'><w:body/></w:document>"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("[Content_Types].xml", types)
        archive.writestr("word/document.xml", document)
        archive.writestr("word/vbaProject.bin", b"inert")
    result = run_native(request_for(source), tmp_path / "out")
    resources = json.loads((_document_dir(result.workspace) / "resources.json").read_text())
    macro = next(item for item in resources["resources"] if item["kind"] == "macro_project")
    assert macro["active"] is True
    security = json.loads((result.workspace / "manifests/security_clearance.json").read_text())
    assert security["active_content_execution_enabled"] is False


def test_zip_path_traversal_is_rejected_by_ds04_or_ds07(tmp_path: Path) -> None:
    source = tmp_path / "unsafe.docx"
    types = CONTENT_TYPES.format(
        items="<Override PartName='/word/document.xml' ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'/>"
    )
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("[Content_Types].xml", types)
        archive.writestr(
            "word/document.xml",
            "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'><w:body/></w:document>",
        )
        archive.writestr("../escape.bin", b"x")
    with pytest.raises(StageFailure) as caught:
        run_native(request_for(source), tmp_path / "out")
    assert caught.value.stage in {"DS04", "DS07"}


def test_unknown_binary_can_complete_only_when_partial_is_allowed(tmp_path: Path) -> None:
    source = tmp_path / "unknown.bin"
    source.write_bytes(bytes(range(256)) * 8)
    strict = request_for(source)
    with pytest.raises(StageFailure) as caught:
        run_native(strict, tmp_path / "strict")
    assert caught.value.stage == "DS08"

    body = {key: value for key, value in strict.items() if key != "header"}
    body["ingestion_policy"] = {**body["ingestion_policy"], "allow_partial": True}
    partial = make_contract("source_ingestion_request", body, producer_version="0.4.0")
    result = run_native(partial, tmp_path / "partial")
    assert (result.workspace / "NATIVE_COMPLETE").is_file()
    decode = json.loads(next((result.workspace / "manifests/decode").glob("*.json")).read_text())
    assert decode["decode_state"] == "failed"
    assert not [
        path
        for path in (result.workspace / "native").iterdir()
        if path.is_dir() and path.name.startswith("document_")
    ]


def test_cancelled_native_extension_resumes_from_completed_preflight(tmp_path: Path) -> None:
    source = tmp_path / "cancel.txt"
    source.write_text("cancel then resume", encoding="utf-8")
    request = request_for(source)
    preflight = run_preflight(request, tmp_path / "out")
    cancel = tmp_path / "CANCEL"
    cancel.write_text("1", encoding="utf-8")
    with pytest.raises(StageFailure) as caught:
        run_native(
            request, tmp_path / "unused", resume_from=preflight.workspace, cancel_file=cancel
        )
    assert caught.value.action_taken == "cancelled"
    cancel.unlink()
    result = run_native(request, tmp_path / "unused", resume_from=preflight.workspace)
    assert (result.workspace / "NATIVE_COMPLETE").is_file()
    assert validate_preflight(result.workspace) == ()


def test_native_profile_reference_tampering_is_detected(tmp_path: Path) -> None:
    source = tmp_path / "tamper.txt"
    source.write_text("tamper", encoding="utf-8")
    result = run_native(request_for(source), tmp_path / "out")
    profile = _document_dir(result.workspace) / "profile.json"
    value = json.loads(profile.read_text())
    value["lines"][0]["text"] = "changed"
    value["header"]["content_hash"] = content_hash(value)
    profile.write_text(json.dumps(value), encoding="utf-8")
    findings = validate_preflight(result.workspace)
    assert any(
        "Hash de référence" in item.message or "SHA-256" in item.message for item in findings
    )

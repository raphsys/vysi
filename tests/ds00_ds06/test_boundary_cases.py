from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from vysi.document_source.contracts_v2.identities import stable_id
from vysi.document_source.execution.contracts import make_contract
from vysi.document_source.execution.coordinator import run_preflight
from vysi.document_source.execution.errors import StageFailure
from vysi.document_source.execution.preflight_validation import validate_preflight

from .helpers import request_for


def test_utf16_text_is_detected_as_text(tmp_path: Path) -> None:
    source = tmp_path / "utf16.txt"
    source.write_text("Bonjour UTF-16", encoding="utf-16")
    result = run_preflight(request_for(source), tmp_path / "out")
    probe = json.loads((result.workspace / "manifests/format_probe_report.json").read_text())
    assert probe["documents"][0]["format_name"] == "txt"


def test_directory_symlink_is_rejected_not_silently_ignored(tmp_path: Path) -> None:
    directory = tmp_path / "folder"
    directory.mkdir()
    real = directory / "real.txt"
    real.write_text("real", encoding="utf-8")
    link = directory / "link.txt"
    try:
        os.symlink(real, link)
    except OSError:
        pytest.skip("symlink unavailable")
    request = request_for(directory)
    body = {k: v for k, v in request.items() if k != "header"}
    body["sources"][0]["kind"] = "directory"
    request = make_contract("source_ingestion_request", body, producer_version="0.3.0")
    with pytest.raises(StageFailure) as caught:
        run_preflight(request, tmp_path / "out")
    assert caught.value.code == "DS-ACQ-001"


def test_request_with_forged_content_hash_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "forged.txt"
    source.write_text("forged", encoding="utf-8")
    request = request_for(source)
    request["header"]["content_hash"] = "0" * 64
    with pytest.raises(StageFailure) as caught:
        run_preflight(request, tmp_path / "out")
    assert caught.value.code == "DS-REQ-001"


def test_url_source_is_rejected_without_network_access(tmp_path: Path) -> None:
    body = {k: v for k, v in request_for(tmp_path / "unused").items() if k != "header"}
    body["sources"] = [
        {
            "locator_id": stable_id("locator", "url"),
            "kind": "url",
            "role": "primary",
            "uri": "https://example.invalid/document.pdf",
            "display_name": "document.pdf",
        }
    ]
    request = make_contract("source_ingestion_request", body, producer_version="0.3.0")
    with pytest.raises(StageFailure) as caught:
        run_preflight(request, tmp_path / "out")
    assert caught.value.code == "DS-ACQ-002"


def test_preflight_validator_detects_tampered_nested_reference(tmp_path: Path) -> None:
    source = tmp_path / "tamper.txt"
    source.write_text("tamper", encoding="utf-8")
    result = run_preflight(request_for(source), tmp_path / "out")
    bundle = result.workspace / "manifests/acquired_source_bundle.json"
    value = json.loads(bundle.read_text())
    value["total_size_bytes"] += 1
    bundle.write_text(json.dumps(value), encoding="utf-8")
    findings = validate_preflight(result.workspace)
    assert any(item.code == "DS-VAL-001" for item in findings)

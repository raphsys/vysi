from __future__ import annotations

import json
from pathlib import Path

import pytest

from vysi.document_source.contracts_v2.identities import stable_id
from vysi.document_source.execution.contracts import make_contract
from vysi.document_source.execution.coordinator import run_preflight
from vysi.document_source.execution.errors import StageFailure

from .helpers import request_for


def test_pdf_encryption_and_signature_are_reported(tmp_path: Path) -> None:
    source = tmp_path / "protected.pdf"
    source.write_bytes(b"%PDF-1.7\n1 0 obj << /Encrypt 2 0 R /Type /Sig /ByteRange [0 1 2 3] >>\n")
    request = request_for(source)
    request["sources"][0]["secret_ref"] = "vault:document-password"
    request = make_contract(
        "source_ingestion_request",
        {k: v for k, v in request.items() if k != "header"},
        producer_version="0.3.0",
    )
    result = run_preflight(request, tmp_path / "out")
    access = json.loads(next((result.workspace / "manifests/access").glob("*.json")).read_text())
    assert access["access_state"] == "secret_required"
    assert access["encryption"]["encrypted"] is True
    assert access["encryption"]["secret_used"] is False
    assert access["encryption"]["secret_ref_audited"] is True
    assert access["signature_state"] == "present_unverified"


def test_injected_bytes_are_acquired_without_uri(tmp_path: Path) -> None:
    locator_id = stable_id("locator", "bytes-test")
    body = {k: v for k, v in request_for(tmp_path / "placeholder").items() if k != "header"}
    body["sources"] = [
        {
            "locator_id": locator_id,
            "kind": "bytes",
            "role": "primary",
            "display_name": "injected.txt",
        }
    ]
    request = make_contract("source_ingestion_request", body, producer_version="0.3.0")
    result = run_preflight(request, tmp_path / "out", bindings={locator_id: b"injected"})
    bundle = json.loads((result.workspace / "manifests/acquired_source_bundle.json").read_text())
    artifact = result.workspace / bundle["artifacts"][0]["stored_path"]
    assert artifact.read_bytes() == b"injected"


def test_expected_hash_mismatch_stops_at_ds02(tmp_path: Path) -> None:
    source = tmp_path / "hash.txt"
    source.write_text("content", encoding="utf-8")
    request = request_for(source)
    request["sources"][0]["expected_sha256"] = "0" * 64
    request = make_contract(
        "source_ingestion_request",
        {k: v for k, v in request.items() if k != "header"},
        producer_version="0.3.0",
    )
    with pytest.raises(StageFailure) as caught:
        run_preflight(request, tmp_path / "out")
    assert caught.value.code == "DS-ACQ-001"
    workspace = next((tmp_path / "out").glob("preflight-*"))
    checkpoint = json.loads((workspace / "execution/checkpoint_manifest.json").read_text())
    assert "DS01" in checkpoint["completed_nodes"]
    assert "DS02" not in checkpoint["completed_nodes"]
    assert not list((workspace / "native/artifacts").glob("*.part"))

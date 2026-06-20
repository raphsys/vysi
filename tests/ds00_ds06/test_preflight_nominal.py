from __future__ import annotations

import json
from pathlib import Path

from vysi.document_source.execution.coordinator import run_preflight
from vysi.document_source.execution.preflight_validation import validate_preflight

from .helpers import request_for


def test_txt_preflight_is_complete_but_not_committed(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    payload = b"Bonjour Vysi\n"
    source.write_bytes(payload)
    request = request_for(source)
    before = json.loads(json.dumps(request))

    result = run_preflight(request, tmp_path / "out")

    assert result.state == "succeeded"
    assert request == before
    assert (result.workspace / "PREFLIGHT_COMPLETE").is_file()
    assert not (result.workspace / "COMMITTED").exists()
    assert validate_preflight(result.workspace) == ()
    bundle = json.loads((result.workspace / "manifests/acquired_source_bundle.json").read_text())
    acquired = result.workspace / bundle["artifacts"][0]["stored_path"]
    assert acquired.read_bytes() == payload
    run = json.loads((result.workspace / "execution/run_manifest.json").read_text())
    assert {node["state"] for node in run["nodes"]} == {"succeeded"}


def test_content_identities_are_stable_across_runs(tmp_path: Path) -> None:
    source = tmp_path / "stable.txt"
    source.write_text("stable", encoding="utf-8")
    request = request_for(source)
    one = run_preflight(request, tmp_path / "one")
    two = run_preflight(request, tmp_path / "two")
    identity_one = json.loads(
        (one.workspace / "manifests/source_identity_manifest.json").read_text()
    )
    identity_two = json.loads(
        (two.workspace / "manifests/source_identity_manifest.json").read_text()
    )
    assert identity_one["logical_documents"] == identity_two["logical_documents"]
    assert one.run_id != two.run_id


def test_complete_checkpoint_resume_is_idempotent(tmp_path: Path) -> None:
    source = tmp_path / "resume.txt"
    source.write_text("resume", encoding="utf-8")
    request = request_for(source)
    first = run_preflight(request, tmp_path / "out")
    run_before = (first.workspace / "execution/run_manifest.json").read_bytes()
    second = run_preflight(request, tmp_path / "unused", resume_from=first.workspace)
    assert second.workspace == first.workspace
    assert second.run_id == first.run_id
    assert (first.workspace / "execution/run_manifest.json").read_bytes() == run_before

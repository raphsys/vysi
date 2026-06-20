from __future__ import annotations

import json
from pathlib import Path

import pytest

from vysi.document_source.execution.coordinator import run_preflight
from vysi.document_source.execution.errors import StageFailure

from .helpers import request_for


def test_cancel_then_resume_same_checkpoint(tmp_path: Path) -> None:
    source = tmp_path / "cancel.txt"
    source.write_text("cancel", encoding="utf-8")
    cancel = tmp_path / "CANCEL"
    cancel.write_text("1")
    request = request_for(source)
    with pytest.raises(StageFailure) as caught:
        run_preflight(request, tmp_path / "out", cancel_file=cancel)
    assert caught.value.action_taken == "cancelled"
    workspace = next((tmp_path / "out").glob("preflight-*"))
    assert not (workspace / "PREFLIGHT_COMPLETE").exists()

    cancel.unlink()
    resumed = run_preflight(request, tmp_path / "unused", resume_from=workspace)
    assert resumed.workspace == workspace
    assert (workspace / "PREFLIGHT_COMPLETE").is_file()
    errors = json.loads((workspace / "execution/error_catalog.json").read_text())
    assert any(item["code"] == "DS-RUN-003" for item in errors["errors"])


def test_missing_source_can_be_fixed_then_resumed_from_ds01(tmp_path: Path) -> None:
    source = tmp_path / "late.txt"
    request = request_for(source)
    with pytest.raises(StageFailure):
        run_preflight(request, tmp_path / "out")
    workspace = next((tmp_path / "out").glob("preflight-*"))
    checkpoint = json.loads((workspace / "execution/checkpoint_manifest.json").read_text())
    assert checkpoint["completed_nodes"] == ["DS01"]

    source.write_text("now present", encoding="utf-8")
    resumed = run_preflight(request, tmp_path / "unused", resume_from=workspace)
    assert resumed.state == "succeeded"
    assert (workspace / "PREFLIGHT_COMPLETE").is_file()

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from ds00_ds06.helpers import request_for
from ds07_ds09.test_native_additional_formats import _minimal_cfb

from vysi.document_source.contracts_v2.canonical import content_hash
from vysi.document_source.contracts_v2.validation import SchemaStore
from vysi.document_source.execution.context import ExecutionContext
from vysi.document_source.execution.coordinator import (
    _default_schema_dir,
    run_quality,
    run_validation,
)
from vysi.document_source.execution.errors import StageFailure
from vysi.document_source.subunits import ds14_validation


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _document_dir(root: Path, name: str) -> Path:
    return next((root / name).glob("document_*"))


def test_ds14_nominal_report_is_commit_eligible_and_not_committed(tmp_path: Path) -> None:
    source = tmp_path / "nominal.txt"
    source.write_text("alpha\nbeta\n", encoding="utf-8")
    result = run_validation(request_for(source), tmp_path / "out")
    report = _json(result.workspace / "validation/validation_report.json")
    checkpoint = _json(result.workspace / "execution/checkpoint_manifest.json")
    manifest = _json(result.workspace / "execution/run_manifest.json")

    assert result.state in {"succeeded", "partial"}
    assert report["package_status"] in {"ok", "review"}
    assert report["commit_eligible"] is True
    assert report["summary"]["blocking_failures"] == 0
    assert report["header"]["schema_version"] == "2.8.0"
    assert report["header"]["status"] == report["package_status"]
    assert checkpoint["header"]["status"] == report["package_status"]
    assert "DS14" in checkpoint["completed_nodes"]
    assert any(
        item["path"] == "validation/validation_report.json"
        for item in checkpoint["artifacts"]
    )
    assert manifest["header"]["status"] == report["package_status"]
    assert (result.workspace / "VALIDATION_COMPLETE").is_file()
    assert not (result.workspace / "COMMITTED").exists()
    assert not (result.workspace / "package_manifest.json").exists()


def test_ds14_reports_tampered_source_bytes_without_publishing_commit(tmp_path: Path) -> None:
    source = tmp_path / "tampered.txt"
    source.write_text("original", encoding="utf-8")
    request = request_for(source)
    quality = run_quality(request, tmp_path / "out")
    bundle = _json(quality.workspace / "manifests/acquired_source_bundle.json")
    artifact = quality.workspace / bundle["artifacts"][0]["stored_path"]
    artifact.write_bytes(b"tampered")

    result = run_validation(request, tmp_path / "unused", resume_from=quality.workspace)
    report = _json(result.workspace / "validation/validation_report.json")

    assert result.state == "error"
    assert report["package_status"] == "error"
    assert report["commit_eligible"] is False
    assert report["summary"]["blocking_failures"] >= 1
    assert any(
        item["status"] == "fail" and "Octets source" in item["message"]
        for item in report["checks"]
    )
    assert (result.workspace / "VALIDATION_COMPLETE").is_file()
    assert not (result.workspace / "COMMITTED").exists()


def test_ds14_reports_contract_hash_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "contract.txt"
    source.write_text("contract", encoding="utf-8")
    request = request_for(source)
    quality = run_quality(request, tmp_path / "out")
    coverage_path = _document_dir(quality.workspace, "quality") / "feature_coverage_report.json"
    coverage = _json(coverage_path)
    coverage["axis_scores"]["binary"] = 0.5
    coverage_path.write_text(json.dumps(coverage, sort_keys=True) + "\n", encoding="utf-8")

    result = run_validation(request, tmp_path / "unused", resume_from=quality.workspace)
    report = _json(result.workspace / "validation/validation_report.json")
    assert result.state == "error"
    assert report["commit_eligible"] is False
    assert any(item["kind"] == "hash" and item["status"] == "fail" for item in report["checks"])


def test_ds14_reports_orphan_reference(tmp_path: Path) -> None:
    source = tmp_path / "orphan.txt"
    source.write_text("orphan", encoding="utf-8")
    request = request_for(source)
    quality = run_quality(request, tmp_path / "out")
    styles = _document_dir(quality.workspace, "native") / "styles.json"
    styles.unlink()

    result = run_validation(request, tmp_path / "unused", resume_from=quality.workspace)
    report = _json(result.workspace / "validation/validation_report.json")
    assert report["package_status"] == "error"
    assert report["commit_eligible"] is False
    assert any(item["status"] == "fail" for item in report["checks"])


def test_ds14_strict_legacy_document_is_rejected_not_operational_error(tmp_path: Path) -> None:
    source = tmp_path / "legacy.doc"
    source.write_bytes(_minimal_cfb())
    request = request_for(
        source,
        strictness_policy={
            "mode": "strict",
            "major_loss_action": "reject",
            "minor_loss_action": "review",
        },
    )
    result = run_validation(request, tmp_path / "out")
    report = _json(result.workspace / "validation/validation_report.json")

    assert result.state == "rejected"
    assert report["package_status"] == "rejected"
    assert report["commit_eligible"] is False
    assert report["document_results"][0]["status"] == "rejected"
    assert not (result.workspace / "COMMITTED").exists()



def test_ds14_missing_identity_produces_a_blocking_report(tmp_path: Path) -> None:
    source = tmp_path / "identity.txt"
    source.write_text("identity", encoding="utf-8")
    request = request_for(source)
    quality = run_quality(request, tmp_path / "out")
    (quality.workspace / "manifests/source_identity_manifest.json").unlink()

    result = run_validation(request, tmp_path / "unused", resume_from=quality.workspace)
    report = _json(result.workspace / "validation/validation_report.json")

    assert result.state == "error"
    assert report["package_status"] == "error"
    assert report["commit_eligible"] is False
    assert report["summary"]["documents_total"] == 0
    assert any(
        item["kind"] == "identity"
        and item["status"] == "fail"
        and "SourceIdentityManifest absent" in item["message"]
        for item in report["checks"]
    )


def test_ds14_document_result_references_its_validation_errors(tmp_path: Path) -> None:
    source = tmp_path / "legacy-errors.doc"
    source.write_bytes(_minimal_cfb())
    request = request_for(
        source,
        strictness_policy={
            "mode": "strict",
            "major_loss_action": "reject",
            "minor_loss_action": "review",
        },
    )
    result = run_validation(request, tmp_path / "out")
    report = _json(result.workspace / "validation/validation_report.json")
    document = report["document_results"][0]

    assert document["status"] == "rejected"
    assert document["error_refs"]
    assert set(document["error_refs"]).issubset(set(report["error_refs"]))

def test_ds14_cancellation_then_resume(tmp_path: Path) -> None:
    source = tmp_path / "resume.txt"
    source.write_text("resume", encoding="utf-8")
    request = request_for(source)
    quality = run_quality(request, tmp_path / "out")
    cancel = tmp_path / "CANCEL"
    cancel.write_text("1", encoding="utf-8")

    with pytest.raises(StageFailure) as caught:
        run_validation(
            request,
            tmp_path / "unused",
            resume_from=quality.workspace,
            cancel_file=cancel,
        )
    assert caught.value.code == "DS-RUN-003"
    assert not (quality.workspace / "VALIDATION_COMPLETE").exists()

    cancel.unlink()
    completed = run_validation(request, tmp_path / "unused", resume_from=quality.workspace)
    assert (completed.workspace / "VALIDATION_COMPLETE").is_file()
    assert _json(completed.workspace / "validation/validation_report.json")[
        "commit_eligible"
    ] is True


def test_ds14_budget_is_checked_before_validation(tmp_path: Path) -> None:
    source = tmp_path / "budget.txt"
    source.write_text("budget", encoding="utf-8")
    request = request_for(source)
    quality = run_quality(request, tmp_path / "out")
    policy = _json(quality.workspace / "request/policy_set.json")
    ctx = ExecutionContext(
        quality.workspace,
        SchemaStore(_default_schema_dir()),
        quality.run_id,
        "0.8.1",
    )
    ctx.max_wall_seconds = -1.0
    with pytest.raises(StageFailure) as caught:
        ds14_validation.execute(ctx, policy)
    assert caught.value.code == "DS-LIM-001"


def test_ds14_completed_resume_is_idempotent(tmp_path: Path) -> None:
    source = tmp_path / "idempotent.txt"
    source.write_text("idempotent", encoding="utf-8")
    request = request_for(source)
    first = run_validation(request, tmp_path / "out")
    report_path = first.workspace / "validation/validation_report.json"
    before = _sha(report_path)
    second = run_validation(request, tmp_path / "unused", resume_from=first.workspace)
    assert second.workspace == first.workspace
    assert _sha(report_path) == before



def test_ds14_completed_rejected_resume_preserves_rejected_state(tmp_path: Path) -> None:
    source = tmp_path / "resume-rejected.doc"
    source.write_bytes(_minimal_cfb())
    request = request_for(
        source,
        strictness_policy={
            "mode": "strict",
            "major_loss_action": "reject",
            "minor_loss_action": "review",
        },
    )
    first = run_validation(request, tmp_path / "out")
    second = run_validation(request, tmp_path / "unused", resume_from=first.workspace)

    assert first.state == "rejected"
    assert second.state == "rejected"


def test_ds14_completed_resume_rejects_tampered_validation_report(tmp_path: Path) -> None:
    source = tmp_path / "resume-tampered.txt"
    source.write_text("resume", encoding="utf-8")
    request = request_for(source)
    first = run_validation(request, tmp_path / "out")
    report_path = first.workspace / "validation/validation_report.json"
    report = _json(report_path)
    report["commit_eligible"] = False
    report_path.write_text(json.dumps(report, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(StageFailure, match="ValidationReport achevé altéré"):
        run_validation(request, tmp_path / "unused", resume_from=first.workspace)

def test_ds14_does_not_mutate_quality_or_native_inputs(tmp_path: Path) -> None:
    source = tmp_path / "immutable.txt"
    source.write_text("immutable", encoding="utf-8")
    request = request_for(source)
    quality = run_quality(request, tmp_path / "out")
    protected = [
        _document_dir(quality.workspace, "quality") / "feature_coverage_report.json",
        _document_dir(quality.workspace, "quality") / "preservation_report.json",
        _document_dir(quality.workspace, "native") / "native_document.json",
        _document_dir(quality.workspace, "ir") / "technical_document_ir.json",
    ]
    before = {path: _sha(path) for path in protected}
    run_validation(request, tmp_path / "unused", resume_from=quality.workspace)
    assert {path: _sha(path) for path in protected} == before


def test_validation_report_content_hash_is_canonical(tmp_path: Path) -> None:
    source = tmp_path / "hash.txt"
    source.write_text("hash", encoding="utf-8")
    result = run_validation(request_for(source), tmp_path / "out")
    report = _json(result.workspace / "validation/validation_report.json")
    assert report["header"]["content_hash"] == content_hash(report)


def test_ds14_render_profile_coverage_detects_missing_unexpected_and_duplicate() -> None:
    from vysi.document_source.validation_v2.evaluate import _render_profile_failures

    policy = {
        "mode": "on_demand",
        "profiles": ["source_reference", "technical_preview"],
    }
    failures = _render_profile_failures(
        policy,
        [
            {"requested_profile": "source_reference"},
            {"requested_profile": "source_reference"},
            {"requested_profile": "native_passthrough"},
        ],
    )
    assert any("demandés absents" in item and "technical_preview" in item for item in failures)
    assert any("non demandés" in item and "native_passthrough" in item for item in failures)
    assert any("plusieurs fois" in item and "source_reference" in item for item in failures)

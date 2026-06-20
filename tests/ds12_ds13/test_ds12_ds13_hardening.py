from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Callable
from pathlib import Path

import pytest
from ds00_ds06.helpers import request_for
from ds07_ds09.test_native_additional_formats import _minimal_cfb, _minimal_pdf
from helpers import make_docx, make_pptx, make_xlsx

from vysi.document_source.contracts_v2.canonical import content_hash
from vysi.document_source.contracts_v2.validation import SchemaStore
from vysi.document_source.execution.context import ExecutionContext
from vysi.document_source.execution.coordinator import (
    _default_schema_dir,
    run_ir,
    run_mapping,
    run_quality,
)
from vysi.document_source.execution.errors import StageFailure
from vysi.document_source.execution.verified_inputs import VerifiedInputReader
from vysi.document_source.quality_v2 import QualityError, validate_quality_invariants
from vysi.document_source.representation_v2 import MappingError, validate_mapping_invariants
from vysi.document_source.subunits import ds12_mapping

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZQmcAAAAASUVORK5CYII="
)


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _write_contract(path: Path, value: dict[str, object]) -> None:
    value["header"]["content_hash"] = content_hash(value)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _document_dir(root: Path, name: str) -> Path:
    return next((root / name).glob("document_*"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_text(path: Path) -> None:
    path.write_text("alpha\nbeta\n", encoding="utf-8")


def _make_pdf(path: Path) -> None:
    path.write_bytes(_minimal_pdf())


def _make_ole(path: Path) -> None:
    path.write_bytes(_minimal_cfb())


def _make_png(path: Path) -> None:
    path.write_bytes(PNG_1X1)


@pytest.mark.parametrize(
    ("suffix", "maker", "expected_status"),
    [
        (".txt", _make_text, "ok"),
        (".docx", make_docx, "ok"),
        (".xlsx", make_xlsx, "ok"),
        (".pptx", make_pptx, "ok"),
        (".pdf", _make_pdf, "ok"),
        (".png", _make_png, "ok"),
        (".doc", _make_ole, "review"),
    ],
)
def test_all_native_profiles_reach_quality_complete(
    tmp_path: Path,
    suffix: str,
    maker: Callable[[Path], None],
    expected_status: str,
) -> None:
    source = tmp_path / f"source{suffix}"
    maker(source)
    result = run_quality(request_for(source), tmp_path / "out")
    mapping = _json(
        _document_dir(result.workspace, "mapping") / "representation_mapping_catalog.json"
    )
    coverage = _json(_document_dir(result.workspace, "quality") / "feature_coverage_report.json")
    preservation = _json(_document_dir(result.workspace, "quality") / "preservation_report.json")

    assert result.state == "succeeded"
    assert (result.workspace / "MAPPING_COMPLETE").is_file()
    assert (result.workspace / "QUALITY_COMPLETE").is_file()
    assert not (result.workspace / "COMMITTED").exists()
    assert mapping["header"]["schema_version"] == "2.4.0"
    assert coverage["header"]["schema_version"] == "2.4.0"
    assert preservation["header"]["schema_version"] == "2.4.0"
    assert coverage["header"]["status"] == expected_status
    assert set(coverage["axis_scores"]) == {
        "binary",
        "structural",
        "technical_semantic",
        "style",
        "relationship",
        "visual",
        "interactive",
        "computational",
        "roundtrip",
    }
    assert len(preservation["transitions"]) == 5


def test_ooxml_mapping_uses_exact_part_and_relationship_authorities(tmp_path: Path) -> None:
    for suffix, maker in (("xlsx", make_xlsx), ("pptx", make_pptx)):
        source = tmp_path / f"sample.{suffix}"
        maker(source)
        result = run_mapping(request_for(source), tmp_path / f"out-{suffix}")
        mapping = _json(
            _document_dir(result.workspace, "mapping") / "representation_mapping_catalog.json"
        )
        native_origins = [edge for edge in mapping["mappings"] if edge["target_layer"] == "native"]
        assert native_origins
        assert all(edge["exactness"] == "exact" for edge in native_origins)
        assert all(edge["confidence"] == 1.0 for edge in native_origins)
        assert any(edge["method"] == "native_container_relationship_ref" for edge in native_origins)
        assert mapping["header"]["status"] == "ok"


def test_mapping_edges_are_canonical_deterministic_and_evidenced(tmp_path: Path) -> None:
    source = tmp_path / "canonical.docx"
    make_docx(source)
    result = run_mapping(request_for(source), tmp_path / "out")
    mapping = _json(
        _document_dir(result.workspace, "mapping") / "representation_mapping_catalog.json"
    )
    for edge in mapping["mappings"]:
        assert edge["source_ids"] == sorted(set(edge["source_ids"]))
        assert edge["target_ids"] == sorted(set(edge["target_ids"]))
        assert edge["evidence_refs"] == sorted(set(edge["evidence_refs"]))
        assert edge["producer"] == "vysi.document_source.ds12"
        assert edge["producer_version"] == "0.6.1"
        assert edge["determinism"] == "deterministic"
        assert edge["evidence_refs"]
        assert all(
            not ref.startswith("/") and ".." not in Path(ref).parts for ref in edge["evidence_refs"]
        )
    validate_mapping_invariants(mapping, producer_version="0.6.1")


def test_ds12_rejects_tampered_artifact_bytes(tmp_path: Path) -> None:
    source = tmp_path / "artifact.txt"
    source.write_text("original", encoding="utf-8")
    request = request_for(source)
    ir = run_ir(request, tmp_path / "out")
    bundle = _json(ir.workspace / "manifests/acquired_source_bundle.json")
    artifact_path = ir.workspace / bundle["artifacts"][0]["stored_path"]
    artifact_path.write_bytes(b"tampered")
    with pytest.raises(StageFailure, match="SHA-256") as caught:
        run_mapping(request, tmp_path / "unused", resume_from=ir.workspace)
    assert caught.value.code == "DS-MAP-001"


def test_ds12_rejects_profile_reference_hash_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "profile.txt"
    source.write_text("profile", encoding="utf-8")
    request = request_for(source)
    ir = run_ir(request, tmp_path / "out")
    native_path = _document_dir(ir.workspace, "native") / "native_document.json"
    native = _json(native_path)
    native["profile_ref"]["sha256"] = "0" * 64
    _write_contract(native_path, native)
    with pytest.raises(StageFailure, match="référencé") as caught:
        run_mapping(request, tmp_path / "unused", resume_from=ir.workspace)
    assert caught.value.code == "DS-MAP-001"


def test_ds13_revalidates_mapping_semantics_not_only_json_schema(tmp_path: Path) -> None:
    source = tmp_path / "mapping.txt"
    source.write_text("mapping", encoding="utf-8")
    request = request_for(source)
    mapped = run_mapping(request, tmp_path / "out")
    mapping_path = (
        _document_dir(mapped.workspace, "mapping") / "representation_mapping_catalog.json"
    )
    mapping = _json(mapping_path)
    mapping["mappings"][0]["mapping_id"] = "mapping_falsified"
    _write_contract(mapping_path, mapping)
    with pytest.raises(StageFailure, match="mapping incohérent") as caught:
        run_quality(request, tmp_path / "unused", resume_from=mapped.workspace)
    assert caught.value.code == "DS-COV-001"


def test_required_rendering_is_declared_as_major_missing_capability(tmp_path: Path) -> None:
    source = tmp_path / "render.txt"
    source.write_text("render", encoding="utf-8")
    request = request_for(
        source,
        rendering_policy={"mode": "required", "profiles": ["source_reference"]},
    )
    result = run_quality(request, tmp_path / "out")
    quality_dir = _document_dir(result.workspace, "quality")
    coverage = _json(quality_dir / "feature_coverage_report.json")
    preservation = _json(quality_dir / "preservation_report.json")
    feature = next(
        item for item in coverage["items"] if item["feature"] == "required_source_rendering"
    )
    assert feature["omitted"] == 1
    assert feature["unsupported"] == 1
    assert coverage["axis_scores"]["visual"] == 0.0
    assert coverage["header"]["status"] == "review"
    assert any(item["stage"] == "native_to_rendered" for item in preservation["losses"])


def test_strict_policy_marks_legacy_loss_as_rejected(tmp_path: Path) -> None:
    source = tmp_path / "legacy.doc"
    _make_ole(source)
    request = request_for(
        source,
        strictness_policy={
            "mode": "strict",
            "major_loss_action": "reject",
            "minor_loss_action": "review",
        },
    )
    result = run_quality(request, tmp_path / "out")
    coverage = _json(_document_dir(result.workspace, "quality") / "feature_coverage_report.json")
    assert coverage["header"]["status"] == "rejected"


def test_ds12_and_ds13_cancellation_are_resumable(tmp_path: Path) -> None:
    source = tmp_path / "resume.txt"
    source.write_text("resume", encoding="utf-8")
    request = request_for(source)
    ir = run_ir(request, tmp_path / "out")
    cancel = tmp_path / "CANCEL"
    cancel.write_text("1")
    with pytest.raises(StageFailure) as ds12_cancelled:
        run_mapping(
            request,
            tmp_path / "unused",
            resume_from=ir.workspace,
            cancel_file=cancel,
        )
    assert ds12_cancelled.value.code == "DS-RUN-003"
    cancel.unlink()
    mapped = run_mapping(request, tmp_path / "unused", resume_from=ir.workspace)

    cancel.write_text("1")
    with pytest.raises(StageFailure) as ds13_cancelled:
        run_quality(
            request,
            tmp_path / "unused",
            resume_from=mapped.workspace,
            cancel_file=cancel,
        )
    assert ds13_cancelled.value.code == "DS-RUN-003"
    cancel.unlink()
    completed = run_quality(request, tmp_path / "unused", resume_from=mapped.workspace)
    assert (completed.workspace / "QUALITY_COMPLETE").is_file()


def test_ds12_checks_budget_before_reading_representations(tmp_path: Path) -> None:
    source = tmp_path / "budget.txt"
    source.write_text("budget", encoding="utf-8")
    request = request_for(source)
    ir = run_ir(request, tmp_path / "out")
    policy = _json(ir.workspace / "request/policy_set.json")
    ctx = ExecutionContext(
        ir.workspace,
        SchemaStore(_default_schema_dir()),
        ir.run_id,
        "0.6.1",
    )
    ctx.max_wall_seconds = -1.0
    with pytest.raises(StageFailure) as caught:
        ds12_mapping.execute(ctx, policy)
    assert caught.value.code == "DS-LIM-001"
    assert caught.value.stage == "DS12"


def test_allow_partial_isolates_one_corrupted_document(tmp_path: Path) -> None:
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    (source_dir / "a.txt").write_text("a", encoding="utf-8")
    (source_dir / "b.txt").write_text("b", encoding="utf-8")
    request = request_for(
        source_dir,
        ingestion_policy={"allow_partial": True, "resume": True, "cache": "read_write"},
    )
    request["sources"][0]["kind"] = "directory"
    request["header"]["content_hash"] = content_hash(request)
    ir = run_ir(request, tmp_path / "out")
    ir_paths = sorted((ir.workspace / "ir").glob("document_*/technical_document_ir.json"))
    assert len(ir_paths) == 2
    broken = _json(ir_paths[0])
    broken["units"][0]["kind"] = "tampered_without_hash_update"
    ir_paths[0].write_text(json.dumps(broken), encoding="utf-8")

    result = run_quality(request, tmp_path / "unused", resume_from=ir.workspace)
    assert result.state == "partial"
    assert (
        len(
            list(
                (result.workspace / "mapping").glob(
                    "document_*/representation_mapping_catalog.json"
                )
            )
        )
        == 1
    )
    assert (
        len(list((result.workspace / "quality").glob("document_*/feature_coverage_report.json")))
        == 1
    )
    errors = _json(result.workspace / "execution/error_catalog.json")
    assert errors["header"]["status"] == "review"
    assert any(item["code"] in {"DS-MAP-001", "DS-COV-001"} for item in errors["errors"])


def test_ds12_ds13_do_not_mutate_authoritative_inputs(tmp_path: Path) -> None:
    source = tmp_path / "immutable.docx"
    make_docx(source)
    request = request_for(source)
    ir = run_ir(request, tmp_path / "out")
    roots = [ir.workspace / "manifests", ir.workspace / "native", ir.workspace / "ir"]
    before = {
        path.relative_to(ir.workspace).as_posix(): _sha256(path)
        for root in roots
        for path in root.rglob("*.json")
    }
    run_quality(request, tmp_path / "unused", resume_from=ir.workspace)
    after = {
        path.relative_to(ir.workspace).as_posix(): _sha256(path)
        for root in roots
        for path in root.rglob("*.json")
    }
    assert before == after


def test_verified_input_reader_detects_post_read_mutation(tmp_path: Path) -> None:
    source = tmp_path / "tracked.txt"
    source.write_text("tracked", encoding="utf-8")
    ir = run_ir(request_for(source), tmp_path / "out")
    ctx = ExecutionContext(
        ir.workspace,
        SchemaStore(_default_schema_dir()),
        ir.run_id,
        "0.6.1",
    )
    reader = VerifiedInputReader(ctx, "DS12", "DS-MAP-001")
    path = ir.workspace / "manifests/format_probe_report.json"
    reader.contract(path, "format_probe_report")
    path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(StageFailure, match="Mutation"):
        reader.verify_unchanged()


def test_quality_invariants_reject_incomplete_transition_chain() -> None:
    coverage = {
        "document_id": "document_example",
        "items": [],
        "axis_scores": {
            "binary": None,
            "structural": None,
            "technical_semantic": None,
            "style": None,
            "relationship": None,
            "visual": None,
            "interactive": None,
            "computational": None,
            "roundtrip": 1.0,
        },
    }
    preservation = {
        "document_id": "document_example",
        "transitions": [],
        "losses": [],
        "opaque_preserved_count": 0,
        "roundtrip_risk": "none",
    }
    with pytest.raises(QualityError, match="incomplète"):
        validate_quality_invariants(coverage, preservation)


def test_mapping_invariants_reject_noncanonical_identity(tmp_path: Path) -> None:
    source = tmp_path / "identity.txt"
    source.write_text("identity", encoding="utf-8")
    result = run_mapping(request_for(source), tmp_path / "out")
    mapping = _json(
        _document_dir(result.workspace, "mapping") / "representation_mapping_catalog.json"
    )
    mapping["mappings"][0]["mapping_id"] = "mapping_wrong"
    with pytest.raises(MappingError, match="non déterministe"):
        validate_mapping_invariants(mapping, producer_version="0.6.1")

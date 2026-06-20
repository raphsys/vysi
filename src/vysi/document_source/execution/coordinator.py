from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from vysi.document_source.contracts_v2.canonical import content_hash
from vysi.document_source.contracts_v2.identities import stable_id
from vysi.document_source.contracts_v2.validation import SchemaStore
from vysi.document_source.execution.context import ExecutionContext
from vysi.document_source.execution.contracts import make_contract, validate_and_write, write_json
from vysi.document_source.execution.errors import StageFailure
from vysi.document_source.execution.time import utc_now
from vysi.document_source.subunits import (
    ds01_request,
    ds02_acquisition,
    ds03_probe,
    ds04_security,
    ds05_identity,
    ds06_access,
    ds07_container,
    ds08_decode,
    ds09_native,
    ds10_ir,
    ds11_rendering,
    ds12_mapping,
    ds13_quality,
    ds14_validation,
)

ALL_STAGES = (
    "DS01",
    "DS02",
    "DS03",
    "DS04",
    "DS05",
    "DS06",
    "DS07",
    "DS08",
    "DS09",
    "DS10",
    "DS11",
    "DS12",
    "DS13",
    "DS14",
)
_STAGE_ERROR_CODES = {
    "DS01": "DS-REQ-001",
    "DS02": "DS-ACQ-001",
    "DS03": "DS-PRB-001",
    "DS04": "DS-SEC-001",
    "DS05": "DS-IDN-001",
    "DS06": "DS-ACC-001",
    "DS07": "DS-CNT-001",
    "DS08": "DS-DEC-001",
    "DS09": "DS-NAT-001",
    "DS10": "DS-IR-001",
    "DS11": "DS-RND-001",
    "DS12": "DS-MAP-001",
    "DS13": "DS-COV-001",
    "DS14": "DS-VAL-001",
}


@dataclass(frozen=True)
class PreflightResult:
    workspace: Path
    run_id: str
    state: str
    completed_nodes: tuple[str, ...]


PipelineResult = PreflightResult


def _node(stage: str, state: str = "pending", attempts: int = 0) -> dict[str, Any]:
    return {
        "node_id": stable_id("node", {"stage": stage}),
        "stage": stage,
        "state": state,
        "attempts": attempts,
        "input_hashes": [],
        "output_refs": [],
    }


def _default_schema_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "schemas" / "v2"


def _request_reference(workspace: Path, request: dict[str, Any]) -> dict[str, str]:
    path = workspace / "request/source_ingestion_request.json"
    return {
        "path": "request/source_ingestion_request.json",
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "schema_id": str(request["header"]["schema_id"]),
        "schema_version": str(request["header"]["schema_version"]),
        "contract_id": str(request["header"]["contract_id"]),
    }


def _write_run_manifest(
    ctx: ExecutionContext,
    request_ref: dict[str, str],
    nodes: list[dict[str, Any]],
    started_at: str,
    finished_at: str | None,
    status: str,
    resume_from: str | None,
) -> dict[str, Any]:
    manifest = make_contract(
        "run_manifest",
        {
            "run_id": ctx.run_id,
            "request_ref": request_ref,
            "started_at": started_at,
            "finished_at": finished_at,
            "nodes": nodes,
            "cancellation_requested": status == "cancelled",
            "resume_from_run_id": resume_from,
        },
        status=status,
        producer_version=ctx.producer_version,
        contract_seed={
            "run_id": ctx.run_id,
            "finished": finished_at is not None,
            "nodes": [n["stage"] for n in nodes],
        },
    )
    _, ref = validate_and_write(
        ctx.workspace,
        "execution/run_manifest.json",
        "run_manifest",
        manifest,
        ctx.schemas,
    )
    ctx.references = [item for item in ctx.references if item["path"] != ref["path"]]
    ctx.references.append(ref)
    return manifest


def _write_error_catalog(ctx: ExecutionContext) -> None:
    catalog = make_contract(
        "error_catalog",
        {"run_id": ctx.run_id, "errors": ctx.errors},
        status="review" if ctx.errors else "ok",
        producer_version=ctx.producer_version,
    )
    _, ref = validate_and_write(
        ctx.workspace,
        "execution/error_catalog.json",
        "error_catalog",
        catalog,
        ctx.schemas,
    )
    ctx.references = [item for item in ctx.references if item["path"] != ref["path"]]
    ctx.references.append(ref)


def _write_checkpoint(
    ctx: ExecutionContext,
    request_hash: str,
    *,
    target_stage: str,
    complete: bool,
    status: str | None = None,
) -> None:
    checkpoint = make_contract(
        "checkpoint_manifest",
        {
            "run_id": ctx.run_id,
            "request_hash": request_hash,
            "completed_nodes": sorted(set(ctx.completed_nodes)),
            "artifacts": sorted(ctx.references, key=lambda item: item["path"]),
            "software_version": ctx.producer_version,
            "compatible_until": None,
        },
        status=status or ("ok" if complete else "partial"),
        producer_version=ctx.producer_version,
    )
    validate_and_write(
        ctx.workspace,
        "execution/checkpoint_manifest.json",
        "checkpoint_manifest",
        checkpoint,
        ctx.schemas,
    )
    if complete and target_stage in {
        "DS06",
        "DS07",
        "DS08",
        "DS09",
        "DS10",
        "DS11",
        "DS12",
        "DS13",
        "DS14",
    }:
        (ctx.workspace / "PREFLIGHT_COMPLETE").write_text("DS00-DS06\n", encoding="utf-8")
    if complete and target_stage in {"DS09", "DS10", "DS11", "DS12", "DS13", "DS14"}:
        (ctx.workspace / "NATIVE_COMPLETE").write_text("DS00-DS09\n", encoding="utf-8")
    if complete and target_stage in {"DS10", "DS11", "DS12", "DS13", "DS14"}:
        (ctx.workspace / "IR_COMPLETE").write_text("DS00-DS10\n", encoding="utf-8")
    if complete and target_stage in {"DS11", "DS12", "DS13", "DS14"}:
        (ctx.workspace / "RENDERING_COMPLETE").write_text(
            "DS11 evaluated according to policy\n", encoding="utf-8"
        )
    if complete and target_stage in {"DS12", "DS13", "DS14"}:
        (ctx.workspace / "MAPPING_COMPLETE").write_text("DS00-DS10,DS12\n", encoding="utf-8")
    if complete and target_stage in {"DS13", "DS14"}:
        (ctx.workspace / "QUALITY_COMPLETE").write_text("DS00-DS10,DS12-DS13\n", encoding="utf-8")
    if complete and target_stage == "DS14":
        (ctx.workspace / "VALIDATION_COMPLETE").write_text(
            "DS00-DS14 (DS11 evaluated according to policy)\n", encoding="utf-8"
        )


def _result_state(status: str) -> str:
    try:
        return {
            "ok": "succeeded",
            "review": "partial",
            "rejected": "rejected",
            "error": "error",
            "cancelled": "cancelled",
        }[status]
    except KeyError as exc:
        raise StageFailure(
            "DS-VAL-001",
            "DS14",
            status or "validation_report",
            "Statut ValidationReport inconnu",
        ) from exc


def _completed_validation_state(ctx: ExecutionContext) -> str:
    relative = "validation/validation_report.json"
    reference = next((item for item in ctx.references if item["path"] == relative), None)
    path = ctx.workspace / relative
    if reference is None or not path.is_file() or path.is_symlink():
        raise StageFailure(
            "DS-VAL-001",
            "DS14",
            ctx.run_id,
            "ValidationReport achevé absent ou irrégulier",
        )
    observed_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    if observed_sha != reference["sha256"]:
        raise StageFailure(
            "DS-VAL-001",
            "DS14",
            relative,
            "ValidationReport achevé altéré",
        )
    report = _load_json(path)
    ctx.schemas.validate("validation_report", report)
    header = cast(dict[str, Any], report["header"])
    if header["content_hash"] != content_hash(report):
        raise StageFailure(
            "DS-VAL-001",
            "DS14",
            relative,
            "Hash canonique du ValidationReport achevé invalide",
        )
    for key in ("schema_id", "schema_version", "contract_id"):
        if str(header[key]) != str(reference[key]):
            raise StageFailure(
                "DS-VAL-001",
                "DS14",
                relative,
                f"{key} du ValidationReport achevé incohérent",
            )
    return _result_state(str(report["package_status"]))


def _load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _load_contracts(directory: Path) -> list[dict[str, Any]]:
    if not directory.is_dir():
        return []
    return [
        _load_json(path) for path in sorted(directory.glob("*.json"), key=lambda item: item.name)
    ]


def _resume_context(
    request: dict[str, Any],
    resume_from: Path,
    schemas: SchemaStore,
    producer_version: str,
    cancel_file: Path | None,
    bindings: dict[str, bytes],
    expected_request_hash: str,
    stages: tuple[str, ...],
) -> tuple[ExecutionContext, set[str], list[dict[str, Any]], str, dict[str, str]]:
    checkpoint_path = resume_from / "execution/checkpoint_manifest.json"
    if not checkpoint_path.is_file():
        raise StageFailure("DS-RUN-001", "DS00", str(resume_from), "Checkpoint de reprise absent")
    checkpoint = _load_json(checkpoint_path)
    schemas.validate("checkpoint_manifest", checkpoint)
    if checkpoint["request_hash"] != expected_request_hash:
        raise StageFailure(
            "DS-RUN-001", "DS00", str(resume_from), "Checkpoint incompatible avec la requête"
        )
    if checkpoint.get("software_version") != producer_version:
        raise StageFailure(
            "DS-RUN-001", "DS00", str(resume_from), "Version de checkpoint incompatible"
        )
    run_manifest = _load_json(resume_from / "execution/run_manifest.json")
    schemas.validate("run_manifest", run_manifest)
    run_id = str(checkpoint["run_id"])
    ctx = ExecutionContext(resume_from, schemas, run_id, producer_version, cancel_file, bindings)
    ctx.references = [dict(item) for item in checkpoint["artifacts"]]
    ctx.completed_nodes = [str(item) for item in checkpoint["completed_nodes"] if item != "DS00"]
    errors_path = resume_from / "execution/error_catalog.json"
    if errors_path.is_file():
        errors = _load_json(errors_path)
        ctx.errors = list(errors.get("errors", []))
    completed = set(ctx.completed_nodes)
    nodes = [_node("DS00", "running", 1)]
    for stage in stages:
        nodes.append(
            _node(
                stage,
                "succeeded" if stage in completed else "pending",
                1 if stage in completed else 0,
            )
        )
    request_ref = _request_reference(resume_from, request)
    return ctx, completed, nodes, str(run_manifest["started_at"]), request_ref


def _run(
    request: dict[str, Any],
    output_root: Path,
    *,
    target_stage: str,
    bindings: dict[str, bytes] | None,
    cancel_file: Path | None,
    producer_version: str,
    resume_from: Path | None,
) -> PipelineResult:
    if target_stage not in ALL_STAGES:
        raise ValueError(f"target_stage invalide: {target_stage}")
    stages = ALL_STAGES[: ALL_STAGES.index(target_stage) + 1]
    target_marker = {
        "DS06": "PREFLIGHT_COMPLETE",
        "DS09": "NATIVE_COMPLETE",
        "DS10": "IR_COMPLETE",
        "DS11": "RENDERING_COMPLETE",
        "DS12": "MAPPING_COMPLETE",
        "DS13": "QUALITY_COMPLETE",
        "DS14": "VALIDATION_COMPLETE",
    }[target_stage]
    schemas = SchemaStore(_default_schema_dir())
    schemas.validate("source_ingestion_request", request)
    effective_preview = ds01_request.normalize_request_content(request)
    request_hash = content_hash(effective_preview)
    active_bindings = bindings or {}

    if resume_from is not None:
        ctx, completed, nodes, started_at, request_ref = _resume_context(
            request,
            resume_from,
            schemas,
            producer_version,
            cancel_file,
            active_bindings,
            request_hash,
            stages,
        )
        if (resume_from / target_marker).is_file() and set(stages).issubset(completed):
            completed_state = (
                _completed_validation_state(ctx) if target_stage == "DS14" else "succeeded"
            )
            return PipelineResult(
                resume_from, ctx.run_id, completed_state, tuple(sorted(completed | {"DS00"}))
            )
        workspace = resume_from
        resume_id = ctx.run_id
    else:
        output_root.mkdir(parents=True, exist_ok=True)
        run_id = stable_id("run", {"request_hash": request_hash, "nonce": uuid.uuid4().hex})
        workspace = output_root / f"preflight-{run_id}"
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(parents=True)
        ctx = ExecutionContext(
            workspace, schemas, run_id, producer_version, cancel_file, active_bindings
        )
        completed = set()
        nodes = [_node("DS00", "running", 1), *[_node(stage) for stage in stages]]
        started_at = utc_now()
        resume_id = None
        request_path = workspace / "request/source_ingestion_request.json"
        request_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(request_path, request)
        request_ref = _request_reference(workspace, request)
        ctx.references.append(request_ref)
        _write_run_manifest(ctx, request_ref, nodes, started_at, None, "running", resume_id)

    # Errors persisted by a failed previous attempt remain part of the audit trail,
    # but a successful resume is judged only on errors produced by this attempt.
    # Otherwise every recoverable failure would permanently force the run to
    # ``review`` even after the failing stage has been corrected and rerun.
    historical_error_count = len(ctx.errors)

    normalized: dict[str, Any] | None = None
    policy: dict[str, Any] | None = None
    effective_request = effective_preview
    bundle: dict[str, Any] | None = None
    probe: dict[str, Any] | None = None
    security: dict[str, Any] | None = None
    access: list[dict[str, Any]] = []
    containers: list[dict[str, Any]] = []
    decode_results: list[dict[str, Any]] = []
    validation_report: dict[str, Any] | None = None
    if completed:
        if "DS01" in completed:
            normalized = _load_json(workspace / "request/normalized_source_request.json")
            policy = _load_json(workspace / "request/policy_set.json")
            ctx.configure_budget(policy["resource_budget"])
        if "DS02" in completed:
            bundle = _load_json(workspace / "manifests/acquired_source_bundle.json")
        if "DS03" in completed:
            probe = _load_json(workspace / "manifests/format_probe_report.json")
        if "DS04" in completed:
            security = _load_json(workspace / "manifests/security_clearance.json")
        if "DS06" in completed:
            access = _load_contracts(workspace / "manifests/access")
        if "DS07" in completed:
            containers = _load_contracts(workspace / "manifests/container")
        if "DS08" in completed:
            decode_results = _load_contracts(workspace / "manifests/decode")

    try:
        for index, stage in enumerate(stages, start=1):
            if stage in completed:
                continue
            ctx.check_cancelled(stage)
            nodes[index]["state"] = "running"
            nodes[index]["attempts"] += 1
            nodes[index]["input_hashes"] = sorted({ref["sha256"] for ref in ctx.references})
            _write_run_manifest(ctx, request_ref, nodes, started_at, None, "running", resume_id)
            _write_checkpoint(ctx, request_hash, target_stage=target_stage, complete=False)
            before = {ref["path"] for ref in ctx.references}
            errors_before = len(ctx.errors)
            try:
                if stage == "DS01":
                    normalized, policy, effective_request = ds01_request.execute(ctx, request)
                elif stage == "DS02":
                    assert normalized is not None and policy is not None
                    bundle = ds02_acquisition.execute(ctx, effective_request, normalized, policy)
                elif stage == "DS03":
                    assert bundle is not None
                    probe = ds03_probe.execute(ctx, bundle)
                elif stage == "DS04":
                    assert bundle is not None and probe is not None and policy is not None
                    security = ds04_security.execute(ctx, bundle, probe, policy)
                elif stage == "DS05":
                    assert bundle is not None and probe is not None
                    ds05_identity.execute(ctx, bundle, probe, effective_request)
                elif stage == "DS06":
                    assert bundle is not None and probe is not None and security is not None
                    access = ds06_access.execute(ctx, bundle, probe, security, effective_request)
                elif stage == "DS07":
                    assert bundle is not None and probe is not None and policy is not None
                    containers = ds07_container.execute(ctx, bundle, probe, policy)
                elif stage == "DS08":
                    assert bundle is not None and probe is not None and policy is not None
                    decode_results = ds08_decode.execute(
                        ctx, bundle, probe, containers, access, policy
                    )
                elif stage == "DS09":
                    ds09_native.execute(ctx, decode_results)
                elif stage == "DS10":
                    assert policy is not None
                    ds10_ir.execute(ctx, policy)
                elif stage == "DS11":
                    assert policy is not None
                    ds11_rendering.execute(ctx, policy)
                elif stage == "DS12":
                    assert policy is not None
                    ds12_mapping.execute(ctx, policy)
                elif stage == "DS13":
                    assert policy is not None
                    ds13_quality.execute(ctx, policy)
                elif stage == "DS14":
                    assert policy is not None
                    validation_report = ds14_validation.execute(ctx, policy)
            except StageFailure:
                raise
            except Exception as exc:
                raise StageFailure(
                    _STAGE_ERROR_CODES[stage],
                    stage,
                    ctx.run_id,
                    "Exception convertie à la frontière de sous-unité",
                    repr(exc),
                ) from exc
            nodes[index]["output_refs"] = [
                ref for ref in ctx.references if ref["path"] not in before
            ]
            nodes[index]["state"] = "partial" if len(ctx.errors) > errors_before else "succeeded"
            completed.add(stage)
            _write_error_catalog(ctx)
            _write_run_manifest(ctx, request_ref, nodes, started_at, None, "running", resume_id)
            _write_checkpoint(ctx, request_hash, target_stage=target_stage, complete=False)

        nodes[0]["state"] = "succeeded"
        if "DS00" not in ctx.completed_nodes:
            ctx.completed_nodes.append("DS00")
        _write_error_catalog(ctx)
        if target_stage == "DS14":
            if validation_report is None:
                validation_report = _load_json(workspace / "validation/validation_report.json")
            final_status = str(validation_report["package_status"])
        else:
            final_status = (
                "review"
                if len(ctx.errors) > historical_error_count
                or any(node["state"] == "partial" for node in nodes)
                else "ok"
            )
        _write_run_manifest(ctx, request_ref, nodes, started_at, utc_now(), final_status, resume_id)
        _write_checkpoint(
            ctx,
            request_hash,
            target_stage=target_stage,
            complete=True,
            status=final_status,
        )
        result_state = _result_state(final_status)
        return PipelineResult(
            workspace, ctx.run_id, result_state, tuple(sorted(set(ctx.completed_nodes)))
        )
    except StageFailure as exc:
        ctx.errors.append(exc.to_record())
        for node in nodes:
            if node["stage"] == exc.stage:
                node["state"] = "cancelled" if exc.action_taken == "cancelled" else "failed"
            elif node["state"] == "pending":
                node["state"] = "blocked"
        nodes[0]["state"] = "cancelled" if exc.action_taken == "cancelled" else "failed"
        _write_error_catalog(ctx)
        status = "cancelled" if exc.action_taken == "cancelled" else "error"
        _write_run_manifest(ctx, request_ref, nodes, started_at, utc_now(), status, resume_id)
        _write_checkpoint(
            ctx,
            request_hash,
            target_stage=target_stage,
            complete=False,
            status=status,
        )
        raise
    except Exception as exc:
        failure = StageFailure(
            "DS-RUN-001",
            "DS00",
            ctx.run_id,
            "Erreur non convertie à une frontière de sous-unité",
            repr(exc),
        )
        ctx.errors.append(failure.to_record())
        _write_error_catalog(ctx)
        _write_run_manifest(ctx, request_ref, nodes, started_at, utc_now(), "error", resume_id)
        _write_checkpoint(
            ctx,
            request_hash,
            target_stage=target_stage,
            complete=False,
            status="error",
        )
        raise failure from exc


def run_preflight(
    request: dict[str, Any],
    output_root: Path,
    *,
    bindings: dict[str, bytes] | None = None,
    cancel_file: Path | None = None,
    producer_version: str = "0.8.1",
    resume_from: Path | None = None,
) -> PreflightResult:
    return _run(
        request,
        output_root,
        target_stage="DS06",
        bindings=bindings,
        cancel_file=cancel_file,
        producer_version=producer_version,
        resume_from=resume_from,
    )


def run_native(
    request: dict[str, Any],
    output_root: Path,
    *,
    bindings: dict[str, bytes] | None = None,
    cancel_file: Path | None = None,
    producer_version: str = "0.8.1",
    resume_from: Path | None = None,
) -> PipelineResult:
    return _run(
        request,
        output_root,
        target_stage="DS09",
        bindings=bindings,
        cancel_file=cancel_file,
        producer_version=producer_version,
        resume_from=resume_from,
    )


def run_ir(
    request: dict[str, Any],
    output_root: Path,
    *,
    bindings: dict[str, bytes] | None = None,
    cancel_file: Path | None = None,
    producer_version: str = "0.8.1",
    resume_from: Path | None = None,
) -> PipelineResult:
    return _run(
        request,
        output_root,
        target_stage="DS10",
        bindings=bindings,
        cancel_file=cancel_file,
        producer_version=producer_version,
        resume_from=resume_from,
    )


def run_rendering(
    request: dict[str, Any],
    output_root: Path,
    *,
    bindings: dict[str, bytes] | None = None,
    cancel_file: Path | None = None,
    producer_version: str = "0.8.1",
    resume_from: Path | None = None,
) -> PipelineResult:
    return _run(
        request,
        output_root,
        target_stage="DS11",
        bindings=bindings,
        cancel_file=cancel_file,
        producer_version=producer_version,
        resume_from=resume_from,
    )


def run_mapping(
    request: dict[str, Any],
    output_root: Path,
    *,
    bindings: dict[str, bytes] | None = None,
    cancel_file: Path | None = None,
    producer_version: str = "0.8.1",
    resume_from: Path | None = None,
) -> PipelineResult:
    return _run(
        request,
        output_root,
        target_stage="DS12",
        bindings=bindings,
        cancel_file=cancel_file,
        producer_version=producer_version,
        resume_from=resume_from,
    )


def run_quality(
    request: dict[str, Any],
    output_root: Path,
    *,
    bindings: dict[str, bytes] | None = None,
    cancel_file: Path | None = None,
    producer_version: str = "0.8.1",
    resume_from: Path | None = None,
) -> PipelineResult:
    return _run(
        request,
        output_root,
        target_stage="DS13",
        bindings=bindings,
        cancel_file=cancel_file,
        producer_version=producer_version,
        resume_from=resume_from,
    )


def run_validation(
    request: dict[str, Any],
    output_root: Path,
    *,
    bindings: dict[str, bytes] | None = None,
    cancel_file: Path | None = None,
    producer_version: str = "0.8.1",
    resume_from: Path | None = None,
) -> PipelineResult:
    return _run(
        request,
        output_root,
        target_stage="DS14",
        bindings=bindings,
        cancel_file=cancel_file,
        producer_version=producer_version,
        resume_from=resume_from,
    )

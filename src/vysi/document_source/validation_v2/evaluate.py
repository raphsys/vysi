from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path, PurePosixPath
from typing import Any, cast

from vysi.document_source.contracts_v2.canonical import canonical_payload, content_hash
from vysi.document_source.contracts_v2.identities import stable_id
from vysi.document_source.contracts_v2.validation import ContractValidationError
from vysi.document_source.execution.context import ExecutionContext
from vysi.document_source.execution.errors import StageFailure
from vysi.document_source.rendering_v2 import validate_rendering_invariants

from .models import (
    CheckKind,
    DocumentValidationResult,
    PackageStatus,
    Severity,
    ValidationCheck,
)

_REFERENCE_KEYS = {"path", "sha256", "schema_id", "schema_version", "contract_id"}
_MUTABLE_AFTER_DS14 = {
    "execution/checkpoint_manifest.json",
    "execution/error_catalog.json",
    "execution/run_manifest.json",
}
_MARKERS = {
    "PREFLIGHT_COMPLETE",
    "NATIVE_COMPLETE",
    "IR_COMPLETE",
    "MAPPING_COMPLETE",
    "QUALITY_COMPLETE",
    "RENDERING_COMPLETE",
    "VALIDATION_COMPLETE",
    "COMMITTED",
}
_PUBLIC_ROOTS = (
    "request",
    "manifests",
    "execution",
    "native",
    "ir",
    "mapping",
    "quality",
    "rendered",
    "geometry",
    "assets",
    "conversion",
)
_REQUIRED_COMPLETED = {
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
}
_STATUS_RANK: dict[str, int] = {
    "ok": 0,
    "review": 1,
    "rejected": 2,
    "error": 3,
    "cancelled": 4,
}


class DraftValidationError(ValueError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _portable(path: str) -> bool:
    pure = PurePosixPath(path)
    return bool(path) and not pure.is_absolute() and ".." not in pure.parts and "\\" not in path


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DraftValidationError(f"Objet JSON attendu: {path.as_posix()}")
    return cast(dict[str, Any], value)


def _references(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        if _REFERENCE_KEYS.issubset(value):
            yield cast(dict[str, Any], value)
        for child in value.values():
            yield from _references(child)
    elif isinstance(value, list):
        for child in value:
            yield from _references(child)


def _schema_key(schema_id: str) -> str | None:
    prefix = "document_source."
    if not schema_id.startswith(prefix):
        return None
    return schema_id[len(prefix) :]


def _published_files(workspace: Path) -> list[Path]:
    result: list[Path] = []
    for root_name in _PUBLIC_ROOTS:
        root = workspace / root_name
        if not root.exists():
            continue
        result.extend(path for path in root.rglob("*") if path.is_file())
    for marker in _MARKERS:
        path = workspace / marker
        if path.is_file():
            result.append(path)
    return sorted(set(result), key=lambda item: item.relative_to(workspace).as_posix())


def _snapshot(workspace: Path) -> dict[str, str]:
    return {
        path.relative_to(workspace).as_posix(): _sha256(path)
        for path in _published_files(workspace)
        if path.relative_to(workspace).as_posix() != "validation/validation_report.json"
    }


def _artifact_set_hash(entries: list[dict[str, Any]], auxiliary: dict[str, str]) -> str:
    normalized = {
        "checkpoint_artifacts": sorted(
            (
                {
                    "path": str(item["path"]),
                    "sha256": str(item["sha256"]),
                    "schema_id": str(item["schema_id"]),
                    "schema_version": str(item["schema_version"]),
                    "contract_id": str(item["contract_id"]),
                }
                for item in entries
            ),
            key=lambda item: item["path"],
        ),
        "auxiliary_files": [
            {"path": path, "sha256": sha256}
            for path, sha256 in sorted(auxiliary.items())
            if path not in _MUTABLE_AFTER_DS14 and path not in _MARKERS
        ],
    }
    return hashlib.sha256(canonical_payload(normalized)).hexdigest()


def _status_max(statuses: list[str]) -> PackageStatus:
    if not statuses:
        return "ok"
    return cast(PackageStatus, max(statuses, key=lambda item: _STATUS_RANK[item]))


def _document_paths(document_id: str) -> dict[str, str]:
    base = f"native/{document_id}"
    return {
        "access": f"manifests/access/{document_id}.json",
        "container": f"manifests/container/{document_id}.json",
        "decode": f"manifests/decode/{document_id}.json",
        "native": f"{base}/native_document.json",
        "profile": f"{base}/profile.json",
        "styles": f"{base}/styles.json",
        "relationships": f"{base}/relationships.json",
        "metadata": f"{base}/metadata.json",
        "annotations": f"{base}/annotations.json",
        "resources": f"{base}/resources.json",
        "ir": f"ir/{document_id}/technical_document_ir.json",
        "mapping": f"mapping/{document_id}/representation_mapping_catalog.json",
        "coverage": f"quality/{document_id}/feature_coverage_report.json",
        "preservation": f"quality/{document_id}/preservation_report.json",
    }


def _render_paths(document_id: str) -> dict[str, str]:
    base = f"rendered/{document_id}"
    return {
        "rendered": f"{base}/rendered_view_catalog.json",
        "geometry": f"{base}/geometry_catalog.json",
        "assets": f"{base}/derived_asset_catalog.json",
    }


def _render_profile_failures(
    rendering_policy: dict[str, Any],
    views: list[dict[str, Any]],
) -> list[str]:
    requested_profiles = {str(item) for item in rendering_policy.get("profiles", [])}
    observed_profiles = [str(item.get("requested_profile", "")) for item in views]
    observed_profile_set = set(observed_profiles)
    failures: list[str] = []
    missing_profiles = sorted(requested_profiles - observed_profile_set)
    unexpected_profiles = sorted(observed_profile_set - requested_profiles)
    duplicate_profiles = sorted(
        profile for profile in observed_profile_set if observed_profiles.count(profile) > 1
    )
    if missing_profiles:
        failures.append(f"profils demandés absents: {missing_profiles}")
    if unexpected_profiles:
        failures.append(f"profils non demandés publiés: {unexpected_profiles}")
    if duplicate_profiles:
        failures.append(f"profils publiés plusieurs fois: {duplicate_profiles}")
    return failures


def evaluate_draft_package(
    ctx: ExecutionContext,
    policy: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    ctx.check_cancelled("DS14")
    workspace = ctx.workspace
    before = _snapshot(workspace)
    checkpoint_path = workspace / "execution/checkpoint_manifest.json"
    policy_path = workspace / "request/policy_set.json"
    if not checkpoint_path.is_file() or not policy_path.is_file():
        raise DraftValidationError("Checkpoint ou politique d'exécution absent")

    checkpoint_sha256 = _sha256(checkpoint_path)
    checkpoint = _load_json(checkpoint_path)
    try:
        ctx.schemas.validate("checkpoint_manifest", checkpoint)
    except ContractValidationError as exc:
        raise DraftValidationError(str(exc)) from exc
    if str(checkpoint["header"]["content_hash"]) != content_hash(checkpoint):
        raise DraftValidationError("Hash canonique du checkpoint invalide")
    if str(checkpoint["run_id"]) != ctx.run_id:
        raise DraftValidationError("run_id du checkpoint incohérent")

    policy_ref = next(
        (
            cast(dict[str, Any], item)
            for item in checkpoint["artifacts"]
            if str(item["path"]) == "request/policy_set.json"
        ),
        None,
    )
    if policy_ref is None:
        raise DraftValidationError("Référence de politique absente du checkpoint")

    checks: list[ValidationCheck] = []
    validation_errors: list[dict[str, Any]] = []
    check_counter = 0

    def add_check(
        *,
        code: str,
        kind: CheckKind,
        scope: str,
        status: str,
        severity: Severity,
        blocking: bool,
        message: str,
        evidence_refs: tuple[str, ...] = (),
    ) -> ValidationCheck:
        nonlocal check_counter
        check_counter += 1
        check_id = stable_id(
            "check",
            {
                "run_id": ctx.run_id,
                "ordinal": check_counter,
                "code": code,
                "kind": kind,
                "scope": scope,
                "status": status,
                "message": message,
            },
        )
        check = ValidationCheck(
            check_id=check_id,
            code=code,
            kind=kind,
            scope=scope,
            status=cast(Any, status),
            severity=severity,
            blocking=blocking,
            message=message,
            evidence_refs=tuple(sorted(set(evidence_refs))),
        )
        checks.append(check)
        if status in {"warning", "fail"}:
            error_code = "DS-VAL-003" if status == "warning" else code
            record = StageFailure(
                error_code,
                "DS14",
                scope,
                message,
                severity=severity,
                retryable=False,
                recoverable=status == "warning",
                action_taken="accepted_with_review" if status == "warning" else "commit_blocked",
            ).to_record()
            record["evidence_refs"] = list(check.evidence_refs)
            validation_errors.append(record)
        return check

    declared_refs = [cast(dict[str, Any], item) for item in checkpoint["artifacts"]]
    declared_by_path = {str(item["path"]): item for item in declared_refs}
    contracts: dict[str, dict[str, Any]] = {}
    adjacency: dict[str, set[str]] = defaultdict(set)
    reference_count = 0
    contract_failures = 0
    hash_failures = 0
    reference_failures = 0

    for reference in sorted(declared_refs, key=lambda item: str(item["path"])):
        ctx.check_cancelled("DS14")
        relative = str(reference["path"])
        if not _portable(relative):
            hash_failures += 1
            add_check(
                code="DS-VAL-001",
                kind="storage",
                scope=relative or "checkpoint",
                status="fail",
                severity="critical",
                blocking=True,
                message="Chemin contractuel non portable",
                evidence_refs=("execution/checkpoint_manifest.json",),
            )
            continue
        target = workspace / relative
        if not target.is_file() or target.is_symlink():
            hash_failures += 1
            add_check(
                code="DS-VAL-001",
                kind="hash",
                scope=relative,
                status="fail",
                severity="critical",
                blocking=True,
                message="Artefact déclaré absent, irrégulier ou symbolique",
                evidence_refs=("execution/checkpoint_manifest.json", relative),
            )
            continue
        observed_sha = _sha256(target)
        if observed_sha != str(reference["sha256"]):
            hash_failures += 1
            add_check(
                code="DS-VAL-001",
                kind="hash",
                scope=relative,
                status="fail",
                severity="critical",
                blocking=True,
                message="SHA-256 de l'artefact déclaré incohérent",
                evidence_refs=("execution/checkpoint_manifest.json", relative),
            )
            continue
        if target.suffix != ".json":
            continue
        try:
            value = _load_json(target)
            header = cast(dict[str, Any], value.get("header", {}))
            schema_id = str(header.get("schema_id", ""))
            schema_key = _schema_key(schema_id)
            if schema_key is None or schema_key not in ctx.schemas.schema_keys:
                raise DraftValidationError(f"Schéma inconnu: {schema_id}")
            ctx.schemas.validate(schema_key, value)
            if str(header.get("content_hash", "")) != content_hash(value):
                raise DraftValidationError("Hash canonique invalide")
            for key in ("schema_id", "schema_version", "contract_id"):
                if str(header.get(key, "")) != str(reference[key]):
                    raise DraftValidationError(f"{key} incohérent avec le checkpoint")
            contracts[relative] = value
        except (OSError, json.JSONDecodeError, ContractValidationError, DraftValidationError) as exc:
            contract_failures += 1
            add_check(
                code="DS-VAL-001",
                kind="schema",
                scope=relative,
                status="fail",
                severity="critical",
                blocking=True,
                message=f"Contrat invalide: {exc}",
                evidence_refs=(relative,),
            )

    if hash_failures == 0:
        add_check(
            code="DS-VAL-001",
            kind="hash",
            scope=ctx.run_id,
            status="pass",
            severity="info",
            blocking=False,
            message=f"{len(declared_refs)} artefacts du checkpoint vérifiés par SHA-256",
            evidence_refs=("execution/checkpoint_manifest.json",),
        )
    if contract_failures == 0:
        add_check(
            code="DS-VAL-001",
            kind="schema",
            scope=ctx.run_id,
            status="pass",
            severity="info",
            blocking=False,
            message=f"{len(contracts)} contrats validés contre leurs schémas et hashes canoniques",
            evidence_refs=tuple(sorted(contracts)),
        )

    for source_path, value in sorted(contracts.items()):
        for nested in _references(value):
            reference_count += 1
            target_path = str(nested["path"])
            adjacency[source_path].add(target_path)
            if not _portable(target_path):
                reference_failures += 1
                add_check(
                    code="DS-VAL-001",
                    kind="reference",
                    scope=source_path,
                    status="fail",
                    severity="critical",
                    blocking=True,
                    message=f"Référence imbriquée non portable: {target_path}",
                    evidence_refs=(source_path,),
                )
                continue
            target = workspace / target_path
            if not target.is_file() or target.is_symlink():
                reference_failures += 1
                add_check(
                    code="DS-VAL-001",
                    kind="reference",
                    scope=source_path,
                    status="fail",
                    severity="critical",
                    blocking=True,
                    message=f"Référence orpheline: {target_path}",
                    evidence_refs=(source_path,),
                )
                continue
            if _sha256(target) != str(nested["sha256"]):
                reference_failures += 1
                add_check(
                    code="DS-VAL-001",
                    kind="reference",
                    scope=source_path,
                    status="fail",
                    severity="critical",
                    blocking=True,
                    message=f"Hash de référence incohérent: {target_path}",
                    evidence_refs=(source_path, target_path),
                )
                continue
            if target.suffix == ".json":
                try:
                    target_value = contracts.get(target_path) or _load_json(target)
                    target_header = cast(dict[str, Any], target_value.get("header", {}))
                    for key in ("schema_id", "schema_version", "contract_id"):
                        if str(target_header.get(key, "")) != str(nested[key]):
                            raise DraftValidationError(f"{key} incohérent")
                except (OSError, json.JSONDecodeError, DraftValidationError) as exc:
                    reference_failures += 1
                    add_check(
                        code="DS-VAL-001",
                        kind="reference",
                        scope=source_path,
                        status="fail",
                        severity="critical",
                        blocking=True,
                        message=f"Métadonnées de référence incohérentes pour {target_path}: {exc}",
                        evidence_refs=(source_path, target_path),
                    )
            if target_path.endswith(".json") and target_path not in declared_by_path:
                reference_failures += 1
                add_check(
                    code="DS-VAL-001",
                    kind="completeness",
                    scope=target_path,
                    status="fail",
                    severity="error",
                    blocking=True,
                    message="Contrat référencé absent de l'inventaire du checkpoint",
                    evidence_refs=(source_path, "execution/checkpoint_manifest.json"),
                )

    if reference_failures == 0:
        add_check(
            code="DS-VAL-001",
            kind="reference",
            scope=ctx.run_id,
            status="pass",
            severity="info",
            blocking=False,
            message=f"{reference_count} références contractuelles vérifiées",
            evidence_refs=("execution/checkpoint_manifest.json",),
        )

    cycle_paths: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str, trail: tuple[str, ...]) -> None:
        if node in visiting:
            cycle_paths.append(" -> ".join((*trail, node)))
            return
        if node in visited:
            return
        visiting.add(node)
        for target in sorted(adjacency.get(node, set())):
            if target in adjacency:
                visit(target, (*trail, node))
        visiting.remove(node)
        visited.add(node)

    for node in sorted(adjacency):
        visit(node, ())
    if cycle_paths:
        add_check(
            code="DS-VAL-001",
            kind="reference",
            scope=ctx.run_id,
            status="fail",
            severity="critical",
            blocking=True,
            message=f"Cycle contractuel interdit détecté: {cycle_paths[0]}",
            evidence_refs=tuple(sorted(adjacency)),
        )
    else:
        add_check(
            code="DS-VAL-001",
            kind="reference",
            scope=ctx.run_id,
            status="pass",
            severity="info",
            blocking=False,
            message="Aucun cycle interdit dans le graphe des références",
            evidence_refs=("execution/checkpoint_manifest.json",),
        )

    bundle = contracts.get("manifests/acquired_source_bundle.json")
    original_failures = 0
    raw_artifact_count = 0
    if bundle is None:
        add_check(
            code="DS-VAL-001",
            kind="completeness",
            scope=ctx.run_id,
            status="fail",
            severity="critical",
            blocking=True,
            message="AcquiredSourceBundle absent",
            evidence_refs=("execution/checkpoint_manifest.json",),
        )
    else:
        for artifact in cast(list[dict[str, Any]], bundle.get("artifacts", [])):
            raw_artifact_count += 1
            relative = str(artifact["stored_path"])
            target = workspace / relative
            if (
                not _portable(relative)
                or not target.is_file()
                or target.is_symlink()
                or target.stat().st_size != int(artifact["size_bytes"])
                or _sha256(target) != str(artifact["sha256"])
            ):
                original_failures += 1
                add_check(
                    code="DS-VAL-001",
                    kind="hash",
                    scope=relative,
                    status="fail",
                    severity="critical",
                    blocking=True,
                    message="Octets source absents ou altérés",
                    evidence_refs=("manifests/acquired_source_bundle.json", relative),
                )
        if original_failures == 0:
            add_check(
                code="DS-VAL-001",
                kind="invariant",
                scope=ctx.run_id,
                status="pass",
                severity="info",
                blocking=False,
                message=f"{raw_artifact_count} artefacts sources préservés avec taille et SHA-256 exacts",
                evidence_refs=("manifests/acquired_source_bundle.json",),
            )

    completed = {str(item) for item in checkpoint.get("completed_nodes", [])}
    missing_completed = sorted(_REQUIRED_COMPLETED - completed)
    marker_evidence = tuple(
        marker
        for marker in (
            "PREFLIGHT_COMPLETE",
            "NATIVE_COMPLETE",
            "IR_COMPLETE",
            "RENDERING_COMPLETE",
            "MAPPING_COMPLETE",
            "QUALITY_COMPLETE",
        )
        if (workspace / marker).is_file()
    )
    required_markers = {
        "PREFLIGHT_COMPLETE",
        "NATIVE_COMPLETE",
        "IR_COMPLETE",
        "RENDERING_COMPLETE",
        "MAPPING_COMPLETE",
        "QUALITY_COMPLETE",
    }
    missing_markers = sorted(required_markers - set(marker_evidence))
    if missing_completed:
        add_check(
            code="DS-VAL-001",
            kind="execution",
            scope=ctx.run_id,
            status="fail",
            severity="critical",
            blocking=True,
            message=f"Draft incomplet; étapes absentes={missing_completed}",
            evidence_refs=("execution/checkpoint_manifest.json", *marker_evidence),
        )
    elif marker_evidence and missing_markers:
        add_check(
            code="DS-VAL-001",
            kind="execution",
            scope=ctx.run_id,
            status="fail",
            severity="critical",
            blocking=True,
            message=f"Marqueurs intermédiaires incohérents; absents={missing_markers}",
            evidence_refs=("execution/checkpoint_manifest.json", *marker_evidence),
        )
    else:
        marker_note = (
            "marqueurs intermédiaires cohérents"
            if marker_evidence
            else "marqueurs différés jusqu'au checkpoint final du run"
        )
        add_check(
            code="DS-VAL-001",
            kind="execution",
            scope=ctx.run_id,
            status="pass",
            severity="info",
            blocking=False,
            message=f"DS01–DS14 avec DS11 évalué selon politique; {marker_note}",
            evidence_refs=("execution/checkpoint_manifest.json", *marker_evidence),
        )

    run_manifest = contracts.get("execution/run_manifest.json")
    if run_manifest is None:
        add_check(
            code="DS-VAL-001",
            kind="execution",
            scope=ctx.run_id,
            status="fail",
            severity="critical",
            blocking=True,
            message="RunManifest absent du draft",
            evidence_refs=("execution/checkpoint_manifest.json",),
        )
    else:
        node_states = {
            str(item["stage"]): str(item["state"])
            for item in cast(list[dict[str, Any]], run_manifest.get("nodes", []))
        }
        invalid_nodes = {
            stage: state
            for stage, state in node_states.items()
            if stage not in {"DS00", "DS14"} and state not in {"succeeded", "partial"}
        }
        ds14_state = node_states.get("DS14")
        if invalid_nodes or ds14_state not in {"running", "succeeded", "partial"}:
            add_check(
                code="DS-VAL-001",
                kind="execution",
                scope=ctx.run_id,
                status="fail",
                severity="critical",
                blocking=True,
                message=f"États de nœuds incohérents: {invalid_nodes}; DS14={ds14_state}",
                evidence_refs=("execution/run_manifest.json",),
            )
        elif any(
            state == "partial"
            for stage, state in node_states.items()
            if stage not in {"DS00", "DS14"}
        ):
            add_check(
                code="DS-VAL-003",
                kind="execution",
                scope=ctx.run_id,
                status="warning",
                severity="warning",
                blocking=False,
                message="Une ou plusieurs étapes amont sont partielles mais auditées",
                evidence_refs=("execution/run_manifest.json",),
            )
        else:
            add_check(
                code="DS-VAL-001",
                kind="execution",
                scope=ctx.run_id,
                status="pass",
                severity="info",
                blocking=False,
                message="États du DAG cohérents jusqu'à DS14",
                evidence_refs=("execution/run_manifest.json",),
            )

    policy_contract = contracts.get("request/policy_set.json")
    if policy_contract is None or content_hash(policy_contract) != content_hash(policy):
        add_check(
            code="DS-VAL-001",
            kind="policy",
            scope=ctx.run_id,
            status="fail",
            severity="critical",
            blocking=True,
            message="Politique effective absente ou différente de celle appliquée",
            evidence_refs=("request/policy_set.json",),
        )
    else:
        add_check(
            code="DS-VAL-001",
            kind="policy",
            scope=ctx.run_id,
            status="pass",
            severity="info",
            blocking=False,
            message="Politique d'acceptation identique à la politique effective du run",
            evidence_refs=("request/policy_set.json",),
        )

    if (workspace / "COMMITTED").exists() or (workspace / "package_manifest.json").exists():
        add_check(
            code="DS-VAL-001",
            kind="storage",
            scope=ctx.run_id,
            status="fail",
            severity="critical",
            blocking=True,
            message="Commit ou PackageManifest détecté avant DS15",
            evidence_refs=tuple(
                item
                for item in ("COMMITTED", "package_manifest.json")
                if (workspace / item).exists()
            ),
        )
    else:
        add_check(
            code="DS-VAL-001",
            kind="storage",
            scope=ctx.run_id,
            status="pass",
            severity="info",
            blocking=False,
            message="Aucun commit ni PackageManifest prématuré",
            evidence_refs=("execution/checkpoint_manifest.json",),
        )

    undeclared_contracts: list[str] = []
    for root_name in _PUBLIC_ROOTS:
        root = workspace / root_name
        if not root.exists():
            continue
        for candidate in sorted(root.rglob("*.json")):
            relative = candidate.relative_to(workspace).as_posix()
            if relative == "execution/checkpoint_manifest.json":
                continue
            try:
                value = _load_json(candidate)
            except (OSError, json.JSONDecodeError, DraftValidationError):
                continue
            if "header" in value and relative not in declared_by_path:
                undeclared_contracts.append(relative)
    if undeclared_contracts:
        add_check(
            code="DS-VAL-001",
            kind="completeness",
            scope=ctx.run_id,
            status="fail",
            severity="error",
            blocking=True,
            message=f"Contrats non déclarés dans le checkpoint: {len(undeclared_contracts)}",
            evidence_refs=tuple(undeclared_contracts),
        )
    else:
        add_check(
            code="DS-VAL-001",
            kind="completeness",
            scope=ctx.run_id,
            status="pass",
            severity="info",
            blocking=False,
            message="Tous les contrats publiés sont inventoriés dans le checkpoint",
            evidence_refs=("execution/checkpoint_manifest.json",),
        )

    security = contracts.get("manifests/security_clearance.json")
    if security is None:
        add_check(
            code="DS-VAL-001",
            kind="security",
            scope=ctx.run_id,
            status="fail",
            severity="critical",
            blocking=True,
            message="SecurityClearance absent",
            evidence_refs=("execution/checkpoint_manifest.json",),
        )
    else:
        decision = str(security.get("decision", "block"))
        safe_execution = (
            security.get("network_enabled") is False
            and security.get("active_content_execution_enabled") is False
        )
        if decision == "block" or not safe_execution:
            add_check(
                code="DS-VAL-002",
                kind="security",
                scope=ctx.run_id,
                status="fail",
                severity="critical",
                blocking=True,
                message="Politique de sécurité bloquante ou exécution active détectée",
                evidence_refs=("manifests/security_clearance.json",),
            )
        elif decision in {"review", "allow_restricted"}:
            add_check(
                code="DS-VAL-003",
                kind="security",
                scope=ctx.run_id,
                status="warning",
                severity="warning",
                blocking=False,
                message=f"Traitement autorisé avec décision de sécurité {decision}",
                evidence_refs=("manifests/security_clearance.json",),
            )
        else:
            add_check(
                code="DS-VAL-001",
                kind="security",
                scope=ctx.run_id,
                status="pass",
                severity="info",
                blocking=False,
                message="Sécurité autorisée, réseau et contenu actif désactivés",
                evidence_refs=("manifests/security_clearance.json",),
            )

    identity = contracts.get("manifests/source_identity_manifest.json")
    if identity is None:
        add_check(
            code="DS-VAL-001",
            kind="identity",
            scope=ctx.run_id,
            status="fail",
            severity="critical",
            blocking=True,
            message="SourceIdentityManifest absent du draft",
            evidence_refs=("execution/checkpoint_manifest.json",),
        )
        logical_documents: list[dict[str, Any]] = []
    else:
        logical_documents = cast(list[dict[str, Any]], identity.get("logical_documents", []))
    document_results: list[DocumentValidationResult] = []
    error_records = list(ctx.errors)
    error_refs_by_scope: dict[str, list[str]] = defaultdict(list)
    for record in error_records:
        error_refs_by_scope[str(record.get("scope", ""))].append(str(record["error_id"]))

    for logical in logical_documents:
        ctx.check_cancelled("DS14")
        document_id = str(logical["document_id"])
        paths = _document_paths(document_id)
        render_paths = _render_paths(document_id)
        doc_check_ids: list[str] = []
        present_render_paths = tuple(path for path in render_paths.values() if path in contracts)
        doc_evidence = tuple(paths.values()) + present_render_paths
        missing = [path for path in paths.values() if path not in contracts]
        if missing:
            check = add_check(
                code="DS-VAL-001",
                kind="completeness",
                scope=document_id,
                status="fail",
                severity="critical",
                blocking=True,
                message=f"Représentations obligatoires absentes: {len(missing)}",
                evidence_refs=tuple(missing),
            )
            doc_check_ids.append(check.check_id)
            doc_status: PackageStatus = "error"
        else:
            check = add_check(
                code="DS-VAL-001",
                kind="completeness",
                scope=document_id,
                status="pass",
                severity="info",
                blocking=False,
                message="Toutes les représentations obligatoires DS06–DS13 sont présentes",
                evidence_refs=doc_evidence,
            )
            doc_check_ids.append(check.check_id)
            doc_status = "ok"

            inconsistent = [
                path
                for path in (
                    paths["access"],
                    paths["container"],
                    paths["decode"],
                    paths["native"],
                    paths["profile"],
                    paths["styles"],
                    paths["relationships"],
                    paths["metadata"],
                    paths["annotations"],
                    paths["resources"],
                    paths["ir"],
                    paths["mapping"],
                    paths["coverage"],
                    paths["preservation"],
                )
                if str(contracts[path].get("document_id", document_id)) != document_id
            ]
            if inconsistent:
                identity_check = add_check(
                    code="DS-VAL-001",
                    kind="identity",
                    scope=document_id,
                    status="fail",
                    severity="critical",
                    blocking=True,
                    message="document_id incohérent entre représentations",
                    evidence_refs=tuple(inconsistent),
                )
                doc_status = "error"
            else:
                identity_check = add_check(
                    code="DS-VAL-001",
                    kind="identity",
                    scope=document_id,
                    status="pass",
                    severity="info",
                    blocking=False,
                    message="Identité documentaire cohérente de DS06 à DS13",
                    evidence_refs=doc_evidence,
                )
            doc_check_ids.append(identity_check.check_id)

            access_state = str(contracts[paths["access"]].get("access_state", "failed"))
            coverage_status = str(contracts[paths["coverage"]]["header"]["status"])
            preservation_status = str(contracts[paths["preservation"]]["header"]["status"])
            document_statuses = [coverage_status, preservation_status]
            if access_state == "blocked":
                document_statuses.append("rejected")
            elif access_state == "failed":
                document_statuses.append("error")
            elif access_state in {"clear_restricted", "secret_required"}:
                document_statuses.append("review")
            doc_status = _status_max(document_statuses)
            if doc_status == "ok":
                quality_check = add_check(
                    code="DS-VAL-001",
                    kind="policy",
                    scope=document_id,
                    status="pass",
                    severity="info",
                    blocking=False,
                    message="Couverture et préservation acceptées sans revue",
                    evidence_refs=(paths["coverage"], paths["preservation"]),
                )
            elif doc_status == "review":
                quality_check = add_check(
                    code="DS-VAL-003",
                    kind="policy",
                    scope=document_id,
                    status="warning",
                    severity="warning",
                    blocking=False,
                    message="Document accepté sous revue explicite par la politique",
                    evidence_refs=(paths["coverage"], paths["preservation"], paths["access"]),
                )
            elif doc_status == "rejected":
                quality_check = add_check(
                    code="DS-VAL-002",
                    kind="policy",
                    scope=document_id,
                    status="fail",
                    severity="error",
                    blocking=True,
                    message="Document rejeté par la politique d'acceptation",
                    evidence_refs=(paths["coverage"], paths["preservation"], paths["access"]),
                )
            else:
                quality_check = add_check(
                    code="DS-VAL-001",
                    kind="policy",
                    scope=document_id,
                    status="fail",
                    severity="critical",
                    blocking=True,
                    message=f"État documentaire non acceptable: {doc_status}",
                    evidence_refs=(paths["coverage"], paths["preservation"], paths["access"]),
                )
            doc_check_ids.append(quality_check.check_id)

            rendering_mode = str(policy["rendering_policy"]["mode"])
            render_missing = [path for path in render_paths.values() if path not in contracts]
            if rendering_mode == "none":
                if present_render_paths:
                    render_check = add_check(
                        code="DS-VAL-001", kind="policy", scope=document_id, status="fail",
                        severity="error", blocking=True,
                        message="Artefacts de rendu présents alors que la politique interdit DS11",
                        evidence_refs=present_render_paths,
                    )
                    doc_status = "error"
                else:
                    render_check = add_check(
                        code="DS-VAL-001", kind="policy", scope=document_id, status="not_applicable",
                        severity="info", blocking=False,
                        message="Rendu source non demandé; absence DS11 conforme",
                        evidence_refs=("request/policy_set.json",),
                    )
            elif render_missing:
                required = rendering_mode == "required"
                render_check = add_check(
                    code="DS-VAL-002" if required else "DS-VAL-003",
                    kind="completeness", scope=document_id,
                    status="fail" if required else "warning",
                    severity="error" if required else "warning", blocking=required,
                    message=f"Catalogues DS11 absents: {len(render_missing)}",
                    evidence_refs=tuple(render_missing),
                )
                doc_status = "rejected" if required else _status_max([doc_status, "review"])
            else:
                rendered_contract = contracts[render_paths["rendered"]]
                geometry_contract = contracts[render_paths["geometry"]]
                assets_contract = contracts[render_paths["assets"]]
                render_doc_ids = {
                    str(rendered_contract.get("document_id", "")),
                    str(geometry_contract.get("document_id", "")),
                    str(assets_contract.get("document_id", "")),
                }
                views = cast(list[dict[str, Any]], rendered_contract.get("views", []))
                surfaces = cast(list[dict[str, Any]], rendered_contract.get("surfaces", []))
                assets_list = cast(list[dict[str, Any]], assets_contract.get("assets", []))
                render_failures: list[str] = []
                if render_doc_ids != {document_id}:
                    render_failures.append("document_id divergent")
                try:
                    validate_rendering_invariants(
                        rendered_contract,
                        geometry_contract,
                        assets_contract,
                    )
                except ValueError as exc:
                    render_failures.append(f"invariant inter-catalogues invalide: {exc}")
                render_failures.extend(
                    _render_profile_failures(
                        cast(dict[str, Any], policy["rendering_policy"]),
                        views,
                    )
                )
                known_assets = {str(item["asset_id"]) for item in assets_list}
                for surface in surfaces:
                    unknown = set(str(item) for item in surface.get("asset_refs", [])) - known_assets
                    if unknown:
                        render_failures.append(f"asset de surface absent: {sorted(unknown)}")
                for asset in assets_list:
                    stored = cast(dict[str, Any], asset.get("stored_ref", {}))
                    relative = str(stored.get("path", ""))
                    target = workspace / relative
                    if (
                        not _portable(relative)
                        or not target.is_file()
                        or target.is_symlink()
                        or target.stat().st_size != int(stored.get("size_bytes", -1))
                        or _sha256(target) != str(stored.get("sha256", ""))
                    ):
                        render_failures.append(f"asset altéré: {relative}")
                unsupported = any(str(item.get("status")) in {"unsupported", "failed"} for item in views)
                required_failure = rendering_mode == "required" and (not surfaces or unsupported)
                if render_failures or required_failure:
                    render_check = add_check(
                        code="DS-VAL-002", kind="completeness", scope=document_id, status="fail",
                        severity="error", blocking=True,
                        message="Rendu DS11 requis incomplet ou incohérent: " + "; ".join(render_failures or ["aucune surface compatible"]),
                        evidence_refs=tuple(render_paths.values()),
                    )
                    doc_status = "rejected"
                elif unsupported or not surfaces:
                    render_check = add_check(
                        code="DS-VAL-003", kind="completeness", scope=document_id, status="warning",
                        severity="warning", blocking=False,
                        message="DS11 exécuté sans surface complète; revue explicite",
                        evidence_refs=tuple(render_paths.values()),
                    )
                    doc_status = _status_max([doc_status, "review"])
                else:
                    clipped_refs = {
                        str(ref)
                        for surface in surfaces
                        for ref in surface.get("clipped_native_unit_refs", [])
                    }
                    omitted_refs = {
                        str(ref)
                        for surface in surfaces
                        for ref in surface.get("omitted_native_unit_refs", [])
                    }
                    not_assessed = any(
                        str(surface.get("fidelity")) == "not_assessed" for surface in surfaces
                    )
                    partial = (
                        any(str(item.get("status")) == "partial" for item in views + surfaces)
                        or bool(clipped_refs)
                        or bool(omitted_refs)
                        or not_assessed
                    )
                    details: list[str] = []
                    if partial:
                        details.append("rendu partiel/revue")
                    if clipped_refs:
                        details.append(f"{len(clipped_refs)} unité(s) partiellement clippée(s)")
                    if omitted_refs:
                        details.append(f"{len(omitted_refs)} unité(s) omise(s)")
                    if not_assessed:
                        details.append("fidélité visuelle non évaluée pour le passthrough")
                    suffix = "; ".join(details)
                    render_check = add_check(
                        code="DS-VAL-003" if partial else "DS-VAL-001",
                        kind="completeness", scope=document_id,
                        status="warning" if partial else "pass",
                        severity="warning" if partial else "info", blocking=False,
                        message=(
                            f"DS11 valide: {len(surfaces)} surface(s), {len(assets_list)} asset(s)"
                            + (f"; {suffix}" if suffix else "")
                        ),
                        evidence_refs=tuple(render_paths.values()),
                    )
                    if partial:
                        doc_status = _status_max([doc_status, "review"])
            doc_check_ids.append(render_check.check_id)

            ir = contracts[paths["ir"]]
            formula_recalculated = any(
                bool(unit.get("technical_properties", {}).get("recalculated"))
                for unit in cast(list[dict[str, Any]], ir.get("units", []))
                if str(unit.get("kind")) == "formula"
            )
            if formula_recalculated:
                formula_check = add_check(
                    code="DS-VAL-001",
                    kind="invariant",
                    scope=document_id,
                    status="fail",
                    severity="critical",
                    blocking=True,
                    message="Formule recalculée implicitement",
                    evidence_refs=(paths["ir"],),
                )
                doc_status = "error"
            else:
                formula_check = add_check(
                    code="DS-VAL-001",
                    kind="invariant",
                    scope=document_id,
                    status="pass",
                    severity="info",
                    blocking=False,
                    message="Aucune formule n'a été recalculée implicitement",
                    evidence_refs=(paths["ir"],),
                )
            doc_check_ids.append(formula_check.check_id)

            mapping = contracts[paths["mapping"]]
            mapping_ids = [str(item["mapping_id"]) for item in mapping.get("mappings", [])]
            deterministic = (
                len(mapping_ids) == len(set(mapping_ids))
                and all(
                    str(item.get("determinism")) == "deterministic"
                    for item in mapping.get("mappings", [])
                )
            )
            if deterministic:
                deterministic_check = add_check(
                    code="DS-VAL-001",
                    kind="determinism",
                    scope=document_id,
                    status="pass",
                    severity="info",
                    blocking=False,
                    message="Mappings déterministes et identifiants uniques",
                    evidence_refs=(paths["mapping"],),
                )
            else:
                deterministic_check = add_check(
                    code="DS-VAL-001",
                    kind="determinism",
                    scope=document_id,
                    status="fail",
                    severity="error",
                    blocking=True,
                    message="Mapping non déterministe ou identifiants dupliqués",
                    evidence_refs=(paths["mapping"],),
                )
                doc_status = "error"
            doc_check_ids.append(deterministic_check.check_id)

        document_results.append(
            DocumentValidationResult(
                document_id=document_id,
                status=doc_status,
                commit_eligible=doc_status in {"ok", "review"}
                and not any(
                    item.blocking and item.scope in {document_id, ctx.run_id}
                    for item in checks
                ),
                check_refs=tuple(sorted(set(doc_check_ids))),
                evidence_refs=tuple(sorted(set(doc_evidence))),
                error_refs=tuple(
                    sorted(
                        set(error_refs_by_scope.get(document_id, []))
                        | {
                            str(record["error_id"])
                            for record in validation_errors
                            if str(record.get("scope", "")) == document_id
                        }
                    )
                ),
            )
        )

    before_after = _snapshot(workspace)
    mutations = [
        path
        for path, before_hash in before.items()
        if before_after.get(path) != before_hash
    ]
    deleted = [path for path in before if path not in before_after]
    if mutations or deleted:
        add_check(
            code="DS-VAL-001",
            kind="invariant",
            scope=ctx.run_id,
            status="fail",
            severity="critical",
            blocking=True,
            message=f"Mutation d'entrée détectée: modifiés={mutations}, supprimés={deleted}",
            evidence_refs=tuple(sorted(set(mutations + deleted))),
        )
    else:
        add_check(
            code="DS-VAL-001",
            kind="invariant",
            scope=ctx.run_id,
            status="pass",
            severity="info",
            blocking=False,
            message="Aucune entrée du draft package n'a été modifiée pendant DS14",
            evidence_refs=("execution/checkpoint_manifest.json",),
        )

    blocking = [item for item in checks if item.blocking]
    warning_checks = [item for item in checks if item.status == "warning"]
    document_status = _status_max([item.status for item in document_results])
    security_blocked = any(
        item.blocking and item.kind in {"security", "policy"} for item in checks
    )
    if blocking:
        package_status: PackageStatus = "rejected" if security_blocked else "error"
    elif document_status in {"rejected", "error", "cancelled"}:
        package_status = document_status
    elif document_status == "review" or warning_checks:
        package_status = "review"
    else:
        package_status = "ok"
    commit_eligible = (
        package_status in {"ok", "review"}
        and not blocking
        and all(item.commit_eligible for item in document_results)
    )

    all_error_records = [*ctx.errors, *validation_errors]
    counts = {status: sum(1 for item in checks if item.status == status) for status in (
        "pass",
        "warning",
        "fail",
        "not_applicable",
    )}
    document_counts = {
        status: sum(1 for item in document_results if item.status == status)
        for status in ("ok", "review", "rejected", "error", "cancelled")
    }
    auxiliary = {
        path: digest
        for path, digest in before.items()
        if path not in declared_by_path
    }
    artifact_paths = {
        str(item["path"])
        for item in declared_refs
    } | {
        path
        for path in auxiliary
        if path not in _MUTABLE_AFTER_DS14 and path not in _MARKERS
    }
    body: dict[str, Any] = {
        "run_id": ctx.run_id,
        "policy_ref": dict(policy_ref),
        "validated_snapshot": {
            "checkpoint_sha256": checkpoint_sha256,
            "artifact_set_sha256": _artifact_set_hash(declared_refs, auxiliary),
            "artifact_count": len(artifact_paths),
            "contract_count": len(contracts),
            "reference_count": reference_count,
        },
        "package_status": package_status,
        "commit_eligible": commit_eligible,
        "summary": {
            "checks_total": len(checks),
            "checks_passed": counts["pass"],
            "checks_warning": counts["warning"],
            "checks_failed": counts["fail"],
            "checks_not_applicable": counts["not_applicable"],
            "blocking_failures": len(blocking),
            "documents_total": len(document_results),
            "documents_ok": document_counts["ok"],
            "documents_review": document_counts["review"],
            "documents_rejected": document_counts["rejected"],
            "documents_error": document_counts["error"],
            "documents_cancelled": document_counts["cancelled"],
            "catalogued_errors": len(all_error_records),
        },
        "checks": [item.to_dict() for item in checks],
        "document_results": [item.to_dict() for item in document_results],
        "error_refs": sorted({str(item["error_id"]) for item in all_error_records}),
    }
    return body, validation_errors

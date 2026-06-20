from __future__ import annotations

import zipfile
from typing import Any

from vysi.document_source.contracts_v2.identities import stable_id
from vysi.document_source.execution.context import ExecutionContext
from vysi.document_source.execution.contracts import make_contract, validate_and_write
from vysi.document_source.security_v2.zip_inspector import inspect_zip


def _error(code: str, scope: str, severity: str, message: str, action: str) -> dict[str, Any]:
    return {
        "error_id": stable_id("error", {"code": code, "scope": scope, "message": message}),
        "code": code,
        "stage": "DS04",
        "scope": scope,
        "severity": severity,
        "message": message,
        "technical_details": "",
        "cause_error_id": None,
        "retryable": False,
        "recoverable": severity != "critical",
        "action_taken": action,
        "evidence_refs": [],
    }


def _limit(name: str, scope: str, configured: int, observed: int, action: str) -> dict[str, Any]:
    return {
        "limit_name": name,
        "scope": scope,
        "configured_value": configured,
        "observed_value": observed,
        "action": action,
    }


def execute(
    ctx: ExecutionContext, bundle: dict[str, Any], probe: dict[str, Any], policy: dict[str, Any]
) -> dict[str, Any]:
    ctx.check_cancelled("DS04")
    budget = policy["resource_budget"]
    findings: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    restrictions = ["network_disabled", "active_content_inert"]
    blocked = False
    review = False

    total = int(bundle.get("total_size_bytes", 0))
    max_source = int(budget["max_source_bytes"])
    action = "allow" if total <= max_source else "block"
    observations.append(_limit("max_source_bytes", "bundle", max_source, total, action))
    if total > max_source:
        findings.append(
            _error(
                "DS-LIM-001",
                "bundle",
                "critical",
                "Taille source cumulée supérieure au budget",
                "blocked",
            )
        )
        blocked = True

    artifacts_by_id = {item["artifact_id"]: item for item in bundle["artifacts"]}
    max_parts = int(budget["max_parts"])
    max_decompressed = int(budget["max_decompressed_bytes"])
    for document in probe["documents"]:
        ctx.check_cancelled("DS04")
        artifact = artifacts_by_id[document["artifact_ids"][0]]
        path = ctx.workspace / artifact["stored_path"]
        if document["container_kind"] in {"ooxml_zip", "zip"}:
            try:
                inspection = inspect_zip(path)
            except (OSError, zipfile.BadZipFile) as exc:
                findings.append(
                    _error(
                        "DS-SEC-001",
                        document["document_id"],
                        "critical",
                        f"ZIP illisible: {exc}",
                        "blocked",
                    )
                )
                blocked = True
                continue
            part_action = "allow" if inspection.entries <= max_parts else "block"
            observations.append(
                _limit(
                    "max_parts", document["document_id"], max_parts, inspection.entries, part_action
                )
            )
            decomp_action = (
                "allow" if inspection.decompressed_bytes <= max_decompressed else "block"
            )
            observations.append(
                _limit(
                    "max_decompressed_bytes",
                    document["document_id"],
                    max_decompressed,
                    inspection.decompressed_bytes,
                    decomp_action,
                )
            )
            if inspection.entries > max_parts or inspection.decompressed_bytes > max_decompressed:
                findings.append(
                    _error(
                        "DS-LIM-001",
                        document["document_id"],
                        "critical",
                        "Budget ZIP dépassé",
                        "blocked",
                    )
                )
                blocked = True
            ratio = inspection.decompressed_bytes / max(inspection.compressed_bytes, 1)
            if ratio > 200 and inspection.decompressed_bytes > 10 * 1024 * 1024:
                findings.append(
                    _error(
                        "DS-SEC-002",
                        document["document_id"],
                        "critical",
                        f"Ratio de compression suspect: {ratio:.1f}",
                        "blocked",
                    )
                )
                blocked = True
            if inspection.unsafe_paths or inspection.duplicate_paths:
                findings.append(
                    _error(
                        "DS-SEC-001",
                        document["document_id"],
                        "critical",
                        "Chemins ZIP dangereux ou dupliqués",
                        "blocked",
                    )
                )
                blocked = True
            if inspection.active_parts:
                findings.append(
                    _error(
                        "DS-SEC-003",
                        document["document_id"],
                        "warning",
                        "Contenu actif inventorié et neutralisé",
                        "inventory_only",
                    )
                )
                restrictions.append("active_content_present_inert")
                review = True
            if inspection.external_parts:
                restrictions.append("external_references_not_resolved")
            if inspection.embedded_parts:
                restrictions.append("embedded_content_inert")
            if inspection.encrypted_entries:
                restrictions.append("zip_encrypted_entries_present")
                review = True
        if document["format_name"] == "unknown_binary":
            findings.append(
                _error(
                    "DS-PRB-002",
                    document["document_id"],
                    "warning",
                    "Format binaire inconnu",
                    "review",
                )
            )
            review = True
        if document.get("extension_mismatch"):
            findings.append(
                _error(
                    "DS-PRB-003",
                    document["document_id"],
                    "warning",
                    "Extension incohérente avec le contenu",
                    "review",
                )
            )
            review = True

    decision = (
        "block"
        if blocked
        else ("review" if review else ("allow_restricted" if restrictions else "allow"))
    )
    status = (
        "rejected"
        if blocked
        else ("review" if decision in {"review", "allow_restricted"} else "ok")
    )
    probe_path = ctx.workspace / "manifests/format_probe_report.json"
    probe_ref = {
        "path": "manifests/format_probe_report.json",
        "sha256": __import__("hashlib").sha256(probe_path.read_bytes()).hexdigest(),
        "schema_id": probe["header"]["schema_id"],
        "schema_version": probe["header"]["schema_version"],
        "contract_id": probe["header"]["contract_id"],
    }
    clearance = make_contract(
        "security_clearance",
        {
            "probe_ref": probe_ref,
            "decision": decision,
            "findings": findings,
            "limit_observations": observations,
            "effective_restrictions": sorted(set(restrictions)),
            "sandbox_profile": "document-source-preflight-v1",
            "network_enabled": False,
            "active_content_execution_enabled": False,
        },
        status=status,
        producer_version=ctx.producer_version,
    )
    _, ref = validate_and_write(
        ctx.workspace,
        "manifests/security_clearance.json",
        "security_clearance",
        clearance,
        ctx.schemas,
    )
    ctx.references.append(ref)
    ctx.errors.extend(findings)
    ctx.completed_nodes.append("DS04")
    return clearance

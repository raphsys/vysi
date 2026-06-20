from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any

from vysi.document_source.execution.context import ExecutionContext
from vysi.document_source.execution.contracts import make_contract, validate_and_write


def _inspect_pdf(path: Path) -> tuple[bool, str | None, list[str], str]:
    with path.open("rb") as handle:
        data = handle.read(16 * 1024 * 1024)
    encrypted = b"/Encrypt" in data
    signature = (
        "present_unverified"
        if b"/ByteRange" in data and (b"/Sig" in data or b"/Type/Sig" in data)
        else "absent"
    )
    restrictions: list[str] = []
    if re.search(rb"/JavaScript\b|/JS\b", data):
        restrictions.append("javascript_present_inert")
    if b"/Launch" in data:
        restrictions.append("launch_action_present_inert")
    return encrypted, "pdf_standard_security" if encrypted else None, restrictions, signature


def _inspect_ooxml(path: Path) -> tuple[bool, str | None, list[str], str]:
    restrictions: list[str] = []
    signature = "absent"
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        lower_names = [name.lower() for name in names]
        if any(name.startswith("_xmlsignatures/") for name in lower_names):
            signature = "present_unverified"
        for name in names:
            lower = name.lower()
            if lower in {"word/settings.xml", "xl/workbook.xml", "ppt/presentation.xml"}:
                with archive.open(name) as handle:
                    payload = handle.read(4 * 1024 * 1024)
                if any(
                    token in payload
                    for token in (
                        b"documentProtection",
                        b"workbookProtection",
                        b"modifyVerifier",
                        b"readOnlyRecommended",
                    )
                ):
                    restrictions.append("native_editing_restriction_present")
            if "externallinks" in lower or lower.endswith(".rels"):
                restrictions.append("external_references_not_resolved")
            if any(token in lower for token in ("vbaproject", "activex")):
                restrictions.append("active_content_present_inert")
    return False, None, sorted(set(restrictions)), signature


def _inspect_ole(path: Path) -> tuple[bool, str | None, list[str], str]:
    with path.open("rb") as handle:
        data = handle.read(32 * 1024 * 1024)
    encrypted = (
        "EncryptedPackage".encode("utf-16le") in data or "EncryptionInfo".encode("utf-16le") in data
    )
    restrictions = ["legacy_ole_partial_inspection"]
    if "VBA".encode("utf-16le") in data:
        restrictions.append("active_content_present_inert")
    return (
        encrypted,
        "agile_or_standard_office_encryption" if encrypted else None,
        restrictions,
        "unknown",
    )


def execute(
    ctx: ExecutionContext,
    bundle: dict[str, Any],
    probe: dict[str, Any],
    security: dict[str, Any],
    request: dict[str, Any],
) -> list[dict[str, Any]]:
    ctx.check_cancelled("DS06")
    artifacts = {item["artifact_id"]: item for item in bundle["artifacts"]}
    locators = {item["locator_id"]: item for item in request["sources"]}
    results: list[dict[str, Any]] = []
    security_restrictions = list(security["effective_restrictions"])
    for document in probe["documents"]:
        ctx.check_cancelled("DS06")
        artifact = artifacts[document["artifact_ids"][0]]
        path = ctx.workspace / artifact["stored_path"]
        if document["format_name"] == "pdf":
            encrypted, scheme, restrictions, signature = _inspect_pdf(path)
        elif document["container_kind"] == "ooxml_zip":
            encrypted, scheme, restrictions, signature = _inspect_ooxml(path)
        elif document["container_kind"] == "ole_cfb":
            encrypted, scheme, restrictions, signature = _inspect_ole(path)
        else:
            encrypted, scheme, restrictions, signature = False, None, [], "absent"
        restrictions = sorted(set(security_restrictions + restrictions))
        encryption_policy = request["security_policy"]["encryption"]
        source_locator = locators.get(str(artifact["source_locator_id"]), {})
        has_secret_ref = bool(source_locator.get("secret_ref"))
        if security["decision"] == "block":
            access_state = "blocked"
        elif encrypted and encryption_policy == "reject":
            access_state = "blocked"
            restrictions.append("encrypted_document_rejected")
        elif encrypted:
            access_state = "secret_required"
            restrictions.append("decryption_deferred")
        elif restrictions:
            access_state = "clear_restricted"
        else:
            access_state = "clear"
        status = (
            "rejected"
            if access_state == "blocked"
            else ("review" if access_state in {"secret_required", "clear_restricted"} else "ok")
        )
        contract = make_contract(
            "access_clearance",
            {
                "document_id": document["document_id"],
                "access_state": access_state,
                "encryption": {
                    "encrypted": encrypted,
                    "scheme": scheme,
                    "secret_used": False,
                    "secret_ref_audited": bool(has_secret_ref),
                },
                "restrictions": sorted(set(restrictions)),
                "signature_state": signature,
                "error_refs": [],
            },
            status=status,
            producer_version=ctx.producer_version,
        )
        relative = f"manifests/access/{document['document_id']}.json"
        _, ref = validate_and_write(
            ctx.workspace, relative, "access_clearance", contract, ctx.schemas
        )
        ctx.references.append(ref)
        results.append(contract)
    ctx.completed_nodes.append("DS06")
    return results

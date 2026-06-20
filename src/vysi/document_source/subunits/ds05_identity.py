from __future__ import annotations

from typing import Any

from vysi.document_source.contracts_v2.canonical import content_hash
from vysi.document_source.execution.context import ExecutionContext
from vysi.document_source.execution.contracts import make_contract, validate_and_write


def execute(
    ctx: ExecutionContext,
    bundle: dict[str, Any],
    probe: dict[str, Any],
    request: dict[str, Any],
) -> dict[str, Any]:
    ctx.check_cancelled("DS05")
    artifacts = {item["artifact_id"]: item for item in bundle["artifacts"]}
    selection_hash = content_hash(request["selection"])
    logical_documents: list[dict[str, Any]] = []
    for document in probe["documents"]:
        identities = [
            (artifacts[item]["ordinal"], artifacts[item]["sha256"], artifacts[item]["role"])
            for item in document["artifact_ids"]
        ]
        logical_documents.append(
            {
                "document_id": document["document_id"],
                "artifact_ids": document["artifact_ids"],
                "content_identity_hash": content_hash(sorted(identities)),
                "selection_hash": selection_hash,
                "parent_document_id": None,
                "embedding_path": None,
            }
        )
    bundle_path = ctx.workspace / "manifests/acquired_source_bundle.json"
    bundle_ref = {
        "path": "manifests/acquired_source_bundle.json",
        "sha256": __import__("hashlib").sha256(bundle_path.read_bytes()).hexdigest(),
        "schema_id": bundle["header"]["schema_id"],
        "schema_version": bundle["header"]["schema_version"],
        "contract_id": bundle["header"]["contract_id"],
    }
    manifest = make_contract(
        "source_identity_manifest",
        {"bundle_ref": bundle_ref, "logical_documents": logical_documents},
        producer_version=ctx.producer_version,
    )
    _, ref = validate_and_write(
        ctx.workspace,
        "manifests/source_identity_manifest.json",
        "source_identity_manifest",
        manifest,
        ctx.schemas,
    )
    ctx.references.append(ref)
    ctx.completed_nodes.append("DS05")
    return manifest

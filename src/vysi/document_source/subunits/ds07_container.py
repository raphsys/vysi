from __future__ import annotations

import hashlib
from typing import Any

from vysi.document_source.container_v2 import inventory_document
from vysi.document_source.execution.context import ExecutionContext
from vysi.document_source.execution.contracts import make_contract, validate_and_write


def _reference_for(ctx: ExecutionContext, relative: str, value: dict[str, Any]) -> dict[str, str]:
    path = ctx.workspace / relative
    return {
        "path": relative,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "schema_id": str(value["header"]["schema_id"]),
        "schema_version": str(value["header"]["schema_version"]),
        "contract_id": str(value["header"]["contract_id"]),
    }


def execute(
    ctx: ExecutionContext,
    bundle: dict[str, Any],
    probe: dict[str, Any],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    ctx.check_cancelled("DS07")
    artifacts = {str(item["artifact_id"]): item for item in bundle["artifacts"]}
    bundle_ref = _reference_for(ctx, "manifests/acquired_source_bundle.json", bundle)
    max_parts = int(policy["resource_budget"]["max_parts"])
    max_decompressed = int(policy["resource_budget"]["max_decompressed_bytes"])
    results: list[dict[str, Any]] = []
    for document in probe["documents"]:
        ctx.check_cancelled("DS07")
        artifact = artifacts[str(document["artifact_ids"][0])]
        source_path = ctx.workspace / str(artifact["stored_path"])
        body = inventory_document(
            source_path,
            artifact,
            document,
            bundle_ref,
            max_parts,
            max_decompressed,
        )
        status = "review" if body.get("warnings") else "ok"
        contract = make_contract(
            "container_part_catalog",
            body,
            status=status,
            producer_version=ctx.producer_version,
        )
        relative = f"manifests/container/{document['document_id']}.json"
        _, ref = validate_and_write(
            ctx.workspace,
            relative,
            "container_part_catalog",
            contract,
            ctx.schemas,
        )
        ctx.references.append(ref)
        results.append(contract)
    ctx.completed_nodes.append("DS07")
    return results

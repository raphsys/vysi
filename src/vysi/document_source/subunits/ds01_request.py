from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from vysi.document_source.contracts_v2.canonical import content_hash
from vysi.document_source.execution.context import ExecutionContext
from vysi.document_source.execution.contracts import make_contract, validate_and_write
from vysi.document_source.execution.errors import StageFailure


def normalize_request_content(request: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(request)
    normalized_sources: list[dict[str, Any]] = []
    for locator in normalized["sources"]:
        item = deepcopy(locator)
        kind = str(item["kind"])
        if kind in {"local_file", "directory", "archive"}:
            uri = item.get("uri")
            if not isinstance(uri, str) or not uri:
                raise StageFailure(
                    "DS-REQ-001",
                    "DS01",
                    str(item.get("locator_id", "unknown")),
                    "URI locale absente",
                )
            item["uri"] = str(Path(uri).expanduser().resolve(strict=False))
        elif kind == "url":
            uri = str(item.get("uri", ""))
            parsed = urlparse(uri)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise StageFailure(
                    "DS-REQ-001", "DS01", str(item.get("locator_id", "unknown")), "URL invalide"
                )
        normalized_sources.append(item)
    if len({item["locator_id"] for item in normalized_sources}) != len(normalized_sources):
        raise StageFailure("DS-REQ-001", "DS01", "request", "locator_id dupliqué")
    normalized["sources"] = normalized_sources
    normalized["header"]["content_hash"] = content_hash(normalized)
    return normalized


def execute(
    ctx: ExecutionContext,
    request: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    ctx.check_cancelled("DS01")
    try:
        ctx.schemas.validate("source_ingestion_request", request)
    except Exception as exc:
        raise StageFailure("DS-REQ-001", "DS01", "request", "Requête invalide", str(exc)) from exc
    observed_hash = content_hash(request)
    if request["header"]["content_hash"] != observed_hash:
        raise StageFailure("DS-REQ-001", "DS01", "request", "content_hash de la requête invalide")

    effective_request = normalize_request_content(request)
    policy_body = {
        "ingestion_policy": deepcopy(effective_request["ingestion_policy"]),
        "security_policy": deepcopy(effective_request["security_policy"]),
        "resource_budget": deepcopy(effective_request["resource_budget"]),
        "rendering_policy": deepcopy(effective_request["rendering_policy"]),
        "preservation_policy": deepcopy(effective_request["preservation_policy"]),
        "strictness_policy": deepcopy(effective_request["strictness_policy"]),
    }
    policy = make_contract("policy_set", policy_body, producer_version=ctx.producer_version)
    _, policy_ref = validate_and_write(
        ctx.workspace, "request/policy_set.json", "policy_set", policy, ctx.schemas
    )

    original_path = ctx.workspace / "request/source_ingestion_request.json"
    request_ref = {
        "path": "request/source_ingestion_request.json",
        "sha256": __import__("hashlib").sha256(original_path.read_bytes()).hexdigest(),
        "schema_id": request["header"]["schema_id"],
        "schema_version": request["header"]["schema_version"],
        "contract_id": request["header"]["contract_id"],
    }
    normalized_body = {
        "request_id": effective_request["request_id"],
        "request_hash": content_hash(effective_request),
        "source_request_ref": request_ref,
        "normalized_sources": effective_request["sources"],
        "normalization_warnings": [],
        "effective_policy_ref": policy_ref,
    }
    normalized_contract = make_contract(
        "normalized_source_request",
        normalized_body,
        producer_version=ctx.producer_version,
        contract_seed={"request_hash": normalized_body["request_hash"]},
    )
    _, normalized_ref = validate_and_write(
        ctx.workspace,
        "request/normalized_source_request.json",
        "normalized_source_request",
        normalized_contract,
        ctx.schemas,
    )
    ctx.references.extend([policy_ref, normalized_ref])
    ctx.configure_budget(policy["resource_budget"])
    ctx.completed_nodes.append("DS01")
    return normalized_contract, policy, effective_request

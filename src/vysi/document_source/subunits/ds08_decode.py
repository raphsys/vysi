from __future__ import annotations

import hashlib
from typing import Any

from vysi.document_source.contracts_v2.identities import stable_id
from vysi.document_source.execution.context import ExecutionContext
from vysi.document_source.execution.contracts import make_contract, validate_and_write
from vysi.document_source.execution.errors import StageFailure
from vysi.document_source.execution.time import utc_now
from vysi.document_source.native_v2 import DecodedPayload, decode_document


def _reference_for(ctx: ExecutionContext, relative: str, value: dict[str, Any]) -> dict[str, str]:
    path = ctx.workspace / relative
    return {
        "path": relative,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "schema_id": str(value["header"]["schema_id"]),
        "schema_version": str(value["header"]["schema_version"]),
        "contract_id": str(value["header"]["contract_id"]),
    }


def _enforce_decode_budget(
    document: dict[str, Any],
    artifact: dict[str, Any],
    container: dict[str, Any],
    policy: dict[str, Any],
) -> None:
    budget = policy["resource_budget"]
    max_memory = int(budget["max_memory_bytes"])
    if max_memory <= 0:
        raise StageFailure(
            "DS-DEC-003", "DS08", str(document["document_id"]), "Budget mémoire invalide"
        )
    format_name = str(document["format_name"])
    artifact_size = int(artifact["size_bytes"])
    # Les lecteurs raw/fixed-layout actuels utilisent une représentation en mémoire.
    if (
        format_name not in {"docx", "docm", "xlsx", "xlsm", "pptx", "pptm"}
        and artifact_size > max_memory // 2
    ):
        raise StageFailure(
            "DS-DEC-003",
            "DS08",
            str(document["document_id"]),
            "Artefact trop volumineux pour le lecteur natif en mémoire",
            f"artifact_size={artifact_size}; max_memory_bytes={max_memory}",
        )
    # Les lecteurs OOXML ne chargent que les parties XML utiles, mais chaque arbre XML
    # doit rester borné par le budget de la requête et la limite absolue du lecteur.
    xml_limit = min(64 * 1024 * 1024, max(1, max_memory // 4))
    for part in container["parts"]:
        if part["part_kind"] not in {"xml", "relationships", "content_types"}:
            continue
        size = int(part.get("size_bytes") or 0)
        if size > xml_limit:
            raise StageFailure(
                "DS-DEC-003",
                "DS08",
                str(part["path"]),
                "Partie XML supérieure au budget de décodage",
                f"part_size={size}; xml_limit={xml_limit}",
            )


def _slot(
    state: str, ref: dict[str, str] | None = None, reasons: list[str] | None = None
) -> dict[str, Any]:
    value: dict[str, Any] = {"state": state, "reason_codes": reasons or []}
    if ref is not None:
        value["ref"] = ref
    return value


def _write_decoded_contracts(
    ctx: ExecutionContext,
    payload: DecodedPayload,
    container: dict[str, Any],
    container_ref: dict[str, str],
) -> dict[str, dict[str, str]]:
    base = f"staging/decode/{payload.document_id}"
    profile = make_contract(
        payload.profile_schema,
        payload.profile_body,
        status="review" if payload.decode_state == "partial" else "ok",
        producer_version=ctx.producer_version,
    )
    _, profile_ref = validate_and_write(
        ctx.workspace,
        f"{base}/profile.json",
        payload.profile_schema,
        profile,
        ctx.schemas,
    )
    part_by_id = {str(item["part_id"]): item for item in container["parts"]}
    opaque_parts: list[dict[str, Any]] = []
    for opaque_id in payload.opaque_part_ids:
        part = part_by_id.get(opaque_id)
        if part is None:
            continue
        opaque_parts.append(
            {
                "opaque_id": opaque_id,
                "source_address": str(part["path"]),
                "reason": "opaque_or_not_semantically_decoded",
                "preserved_ref": container_ref,
            }
        )
    native = make_contract(
        "native_document",
        {
            "document_id": payload.document_id,
            "profile_kind": payload.profile_kind,
            "profile_version": "2.0.0",
            "profile_ref": profile_ref,
            "root_unit_ids": list(payload.root_unit_ids),
            "opaque_parts": opaque_parts,
            "capabilities": list(payload.capabilities),
        },
        status="review" if payload.decode_state == "partial" else "ok",
        producer_version=ctx.producer_version,
    )
    _, native_ref = validate_and_write(
        ctx.workspace,
        f"{base}/native_document.json",
        "native_document",
        native,
        ctx.schemas,
    )
    style = make_contract(
        "native_style_catalog",
        {"document_id": payload.document_id, "styles": list(payload.styles)},
        producer_version=ctx.producer_version,
    )
    _, style_ref = validate_and_write(
        ctx.workspace,
        f"{base}/styles.json",
        "native_style_catalog",
        style,
        ctx.schemas,
    )
    relationships = make_contract(
        "native_relationship_catalog",
        {"document_id": payload.document_id, "relationships": list(payload.relationships)},
        producer_version=ctx.producer_version,
    )
    _, relationships_ref = validate_and_write(
        ctx.workspace,
        f"{base}/relationships.json",
        "native_relationship_catalog",
        relationships,
        ctx.schemas,
    )
    metadata = make_contract(
        "native_metadata_catalog",
        {"document_id": payload.document_id, "items": list(payload.metadata)},
        producer_version=ctx.producer_version,
    )
    _, metadata_ref = validate_and_write(
        ctx.workspace,
        f"{base}/metadata.json",
        "native_metadata_catalog",
        metadata,
        ctx.schemas,
    )
    annotations = make_contract(
        "native_annotation_catalog",
        {"document_id": payload.document_id, "annotations": list(payload.annotations)},
        producer_version=ctx.producer_version,
    )
    _, annotations_ref = validate_and_write(
        ctx.workspace,
        f"{base}/annotations.json",
        "native_annotation_catalog",
        annotations,
        ctx.schemas,
    )
    resources = make_contract(
        "native_resource_catalog",
        {
            "document_id": payload.document_id,
            "resources": list(payload.resources),
            "occurrences": list(payload.occurrences),
        },
        producer_version=ctx.producer_version,
    )
    _, resources_ref = validate_and_write(
        ctx.workspace,
        f"{base}/resources.json",
        "native_resource_catalog",
        resources,
        ctx.schemas,
    )
    refs = {
        "profile": profile_ref,
        "native": native_ref,
        "styles": style_ref,
        "relationships": relationships_ref,
        "metadata": metadata_ref,
        "annotations": annotations_ref,
        "resources": resources_ref,
    }
    ctx.references.extend(refs.values())
    return refs


def execute(
    ctx: ExecutionContext,
    bundle: dict[str, Any],
    probe: dict[str, Any],
    containers: list[dict[str, Any]],
    access: list[dict[str, Any]],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    ctx.check_cancelled("DS08")
    artifacts = {str(item["artifact_id"]): item for item in bundle["artifacts"]}
    containers_by_document = {str(item["document_id"]): item for item in containers}
    access_by_document = {str(item["document_id"]): item for item in access}
    allow_partial = bool(policy["ingestion_policy"]["allow_partial"])
    attempts: list[dict[str, Any]] = []
    decoded: list[
        tuple[dict[str, Any], DecodedPayload | None, dict[str, dict[str, str]] | None, list[str]]
    ] = []
    for document in probe["documents"]:
        ctx.check_cancelled("DS08")
        document_id = str(document["document_id"])
        artifact = artifacts[str(document["artifact_ids"][0])]
        container = containers_by_document[document_id]
        access_item = access_by_document[document_id]
        started = utc_now()
        error_refs: list[str] = []
        _enforce_decode_budget(document, artifact, container, policy)
        payload: DecodedPayload | None = None
        refs: dict[str, dict[str, str]] | None = None
        outcome = "success"
        reader_id = f"vysi.native.{document['format_name']}"
        try:
            payload = decode_document(
                ctx.workspace / str(artifact["stored_path"]),
                document,
                container,
                access_item,
            )
            reader_id = payload.reader_id
            container_ref = _reference_for(
                ctx,
                f"manifests/container/{document_id}.json",
                container,
            )
            refs = _write_decoded_contracts(ctx, payload, container, container_ref)
            outcome = "partial" if payload.decode_state == "partial" else "success"
        except StageFailure as exc:
            if not allow_partial:
                raise
            record = exc.to_record()
            ctx.errors.append(record)
            error_refs.append(str(record["error_id"]))
            outcome = (
                "blocked"
                if access_item["access_state"] in {"blocked", "secret_required"}
                else "failed"
            )
        attempts.append(
            {
                "attempt_id": stable_id(
                    "attempt",
                    {"run_id": ctx.run_id, "document_id": document_id, "reader_id": reader_id},
                ),
                "reader_id": reader_id,
                "reader_version": ctx.producer_version,
                "document_id": document_id,
                "started_at": started,
                "finished_at": utc_now(),
                "outcome": outcome,
                "fallback": False,
                "error_refs": error_refs,
            }
        )
        decoded.append((document, payload, refs, error_refs))

    attempt_catalog = make_contract(
        "reader_attempt_catalog",
        {"run_id": ctx.run_id, "attempts": attempts},
        status="review" if any(item["outcome"] != "success" for item in attempts) else "ok",
        producer_version=ctx.producer_version,
    )
    _, attempt_ref = validate_and_write(
        ctx.workspace,
        "execution/reader_attempt_catalog.json",
        "reader_attempt_catalog",
        attempt_catalog,
        ctx.schemas,
    )
    ctx.references.append(attempt_ref)

    results: list[dict[str, Any]] = []
    for document, payload, refs, error_refs in decoded:
        document_id = str(document["document_id"])
        if payload is None or refs is None:
            state = (
                "blocked"
                if access_by_document[document_id]["access_state"] in {"blocked", "secret_required"}
                else "failed"
            )
            output_slots = {
                name: _slot(
                    "blocked_by_policy" if state == "blocked" else "failed", reasons=["DS-DEC-002"]
                )
                for name in (
                    "native",
                    "styles",
                    "relationships",
                    "metadata",
                    "annotations",
                    "resources",
                )
            }
            profile_kind = "unknown"
            status = "review"
        else:
            state = payload.decode_state
            slot_state = "partial" if state == "partial" else "available"
            reasons = ["DS-DEC-002"] if state == "partial" else []
            output_slots = {
                "native": _slot(slot_state, refs["native"], reasons),
                "styles": _slot("available", refs["styles"]),
                "relationships": _slot("available", refs["relationships"]),
                "metadata": _slot("available", refs["metadata"]),
                "annotations": _slot("available", refs["annotations"]),
                "resources": _slot("available", refs["resources"]),
            }
            profile_kind = payload.profile_kind
            status = "review" if state == "partial" else "ok"
        result = make_contract(
            "native_decode_result",
            {
                "document_id": document_id,
                "reader_attempt_ref": attempt_ref,
                "selected_reader": {
                    "reader_id": payload.reader_id
                    if payload is not None
                    else f"vysi.native.{document['format_name']}",
                    "reader_version": ctx.producer_version,
                    "sandbox_profile": "document-source-inert",
                },
                "profile_kind": profile_kind,
                "decode_state": state,
                "output_slots": output_slots,
                "error_refs": error_refs,
            },
            status=status,
            producer_version=ctx.producer_version,
        )
        _, result_ref = validate_and_write(
            ctx.workspace,
            f"manifests/decode/{document_id}.json",
            "native_decode_result",
            result,
            ctx.schemas,
        )
        ctx.references.append(result_ref)
        results.append(result)
    ctx.completed_nodes.append("DS08")
    return results
